"""Candidate explorer selection, Reset and removal regression tests."""
import json
import numpy as np
import pandas as pd
import pytest

from stellar_streams.dashboard_data import load_results, filter_candidates, display_sample, make_view
from stellar_streams.preprocessing import FEATURES


@pytest.fixture
def saved(tmp_path):
    folder = tmp_path / "saved"
    folder.mkdir()
    stars = pd.DataFrame({"source_id": [str(900000000000000001 + i) for i in range(8)],
        "cluster_id": [0, 0, 0, 1, 1, -1, -1, -1], "membership_strength": [.9] * 5 + [0.] * 3,
        "ra": np.arange(8), "dec": np.arange(8), "umap_1": np.arange(8), "umap_2": np.arange(8)})
    for i, col in enumerate(FEATURES):
        stars[col] = np.arange(8) + i
    stars.to_csv(folder / "assigned_stars.csv", index=False)
    pd.DataFrame({"cluster_id": [0, 1], "n_members": [3, 2], "seed_jaccard_mean": [.8, np.nan]}).to_csv(folder / "candidate_catalog.csv", index=False)
    (folder / "summary.json").write_text(json.dumps({"config": {"seed": 42, "plot_max_stars": 3}, "data_kind": "synthetic_toy"}))
    return folder


def callback_post(app, starts, values, changed):
    key = next(k for k in app.callback_map if k.startswith(starts))
    meta = app.callback_map[key]
    def item(x):
        return {**x, "value": values.get((x["id"], x["property"]))}
    outputs = meta["output"]
    payload = {"output": key, "outputs": [{"id": o.component_id, "property": o.component_property} for o in outputs],
               "inputs": [item(x) for x in meta["inputs"]], "state": [item(x) for x in meta["state"]], "changedPropIds": [changed]}
    response = app.server.test_client().post("/_dash-update-component", json=payload)
    assert response.status_code == 200, response.data
    return response.get_json()["response"]


def settings():
    return {("method", "value"): "saved", ("candidate", "value"): "0", ("min-size", "value"): 0,
            ("min-seed", "value"): 0, ("min-direct", "value"): 0, ("min-persistence", "value"): 0,
            ("color", "value"): "candidate", ("cap", "value"): 3, ("noise", "value"): ["show"],
            ("source", "value"): "", ("reset", "n_clicks"): 0}


def app_for(saved, **kwargs):
    pytest.importorskip("dash")
    from stellar_streams.dashboard import create_app
    return create_app(saved, **kwargs)


def test_display_sampling_and_linked_exact_ids(saved):
    data = load_results(saved)
    original = data.stars.copy(deep=True)
    sampled, counts = display_sample(data, [0, 1], candidate="0", cap=4)
    assert counts["candidate_total"] == 3 and counts["candidate_rendered"] > 0
    assert len(sampled) <= 4
    missing = next(s for s in data.stars.source_id if s not in set(sampled.source_id))
    searched, _ = display_sample(data, [], source=missing, show_noise=False, cap=1)
    assert searched.source_id.tolist() == [missing]
    for view in ("position", "embedding", "sky", "velocity"):
        figure = make_view(data, searched, view)
        assert any(t.name == "Searched source" and t.customdata[0][0] == missing for t in figure.data)
        assert all(isinstance(point[0], str) for t in json.loads(figure.to_json())["data"] for point in t["customdata"])
    assert make_view(data, sampled, "embedding").data[0].type == "scattergl"
    assert make_view(data, sampled, "position").data[0].type == "scatter3d"
    pd.testing.assert_frame_equal(data.stars, original)
    assert filter_candidates(data, seed=.5).cluster_id.tolist() == [0]
    assert filter_candidates(data, direct=.5).empty


def test_full_display_cap_preserves_every_selected_source_across_views(saved):
    data = load_results(saved)
    original_stars = data.stars.copy(deep=True)
    original_catalog = data.catalog.copy(deep=True)
    expected_ids = set(data.stars.source_id)
    displayed, counts = display_sample(data, data.catalog.cluster_id, candidate="0",
                                       show_noise=True, cap=len(data.stars))
    assert len(displayed) == len(data.stars)
    assert displayed.source_id.is_unique
    assert set(displayed.source_id) == expected_ids
    assert counts["total"] == counts["visible"] == counts["rendered"] == len(data.stars)
    assert counts["candidate_rendered"] == counts["candidate_total"] == 3
    assert (displayed.cluster_id < 0).sum() == 3
    for view in ("position", "embedding", "sky", "velocity"):
        figure = make_view(data, displayed, view, focused=True)
        plotted_ids = [point[0] for trace in figure.data for point in trace.customdata]
        assert len(plotted_ids) == len(expected_ids)
        assert set(plotted_ids) == expected_ids
    pd.testing.assert_frame_equal(data.stars, original_stars)
    pd.testing.assert_frame_equal(data.catalog, original_catalog)


def test_raising_cap_overrides_saved_display_sample_without_refitting(saved):
    app = app_for(saved)  # saved plot_max_stars is three, full selected sample is eight
    values = settings()
    values[("candidate", "value")] = None
    sampled = callback_post(app, "..position.figure", values, "cap.value")
    assert "3 rendered" in sampled["counts"]["children"]
    values[("cap", "value")] = 8
    full = callback_post(app, "..position.figure", values, "cap.value")
    assert "8 total selected stars" in full["counts"]["children"]
    assert "8 rendered" in full["counts"]["children"]
    expected_ids = set(app.result_data["saved"].stars.source_id)
    for view in ("position", "embedding", "sky", "velocity"):
        plotted_ids = [point[0] for trace in full[view]["figure"]["data"] for point in trace["customdata"]]
        assert len(plotted_ids) == len(expected_ids)
        assert set(plotted_ids) == expected_ids
    assert app.result_data["saved"].summary["config"]["plot_max_stars"] == 3


def test_removed_sections_callbacks_and_legacy_files(saved):
    # Obsolete evidence files no longer affect an explorer-only app.
    (saved / "reference_matches.csv").write_text("invalid legacy content")
    app = app_for(saved)
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    layout = client.get("/_dash-layout").data
    for text in (b"Algorithm comparison", b"Published-stream reference", b"Download evidence", b"Clear candidate"):
        assert text not in layout
    assert b'"id":"reset"' in layout
    assert not any("download" in key or "coverage" in key or "best" in key for key in app.callback_map)
    assert b"https://cdn.plot.ly" not in client.get("/").data


def test_table_selection_and_full_sample_lookup(saved):
    app = app_for(saved, display_cap=3)
    values = settings()
    selected = callback_post(app, "..candidates.data", values, "candidate.value")
    assert selected["candidate"]["value"] == "0"
    values[("candidates", "active_cell")] = {"row_id": "1", "row": 0, "column": 0, "column_id": "cluster_id"}
    selected = callback_post(app, "..candidates.data", values, "candidates.active_cell")
    assert selected["candidate"]["value"] == "1"
    values[("source", "value")] = "900000000000000008"
    values[("noise", "value")] = []
    response = callback_post(app, "..position.figure", values, "source.value")
    for graph in ["position", "embedding", "sky", "velocity"]:
        point = next(t for t in response[graph]["figure"]["data"] if t["name"] == "Searched source")
        assert point["customdata"][0][0] == "900000000000000008"
    assert "Catalog highlight" not in response["counts"]["children"]


def test_reset_restores_table_search_selection_and_views(saved):
    app = app_for(saved, display_cap=5)
    values = settings()
    values.update({("reset", "n_clicks"): 1, ("color", "value"): "z_kpc", ("source", "value"): "900000000000000008",
                   ("min-size", "value"): 4, ("cap", "value"): 2, ("noise", "value"): [],
                   ("candidates", "active_cell"): {"row_id": "1", "row": 0, "column": 0}})
    reset = callback_post(app, "..method.value", values, "reset.n_clicks")
    assert reset["method"]["value"] == "saved"
    assert reset["color"]["value"] == "candidate"
    assert reset["source"]["value"] == ""
    assert reset["noise"]["value"] == ["show"]
    assert reset["candidates"] == {"filter_query": "", "sort_by": [], "page_current": 0}
    assert reset["candidate"]["search_value"] == ""
    for view in ("position", "embedding", "sky", "velocity"):
        assert reset[view] == {"relayoutData": None, "selectedData": None, "clickData": None}
    chosen = callback_post(app, "..candidates.data", values, "reset.n_clicks")
    assert chosen["candidate"]["value"] is None
    assert chosen["candidates"]["active_cell"] is None
    # Numeric resets are synchronous clientside callbacks; browser smoke test
    # checks their values. Changed revision is how Plotly resets camera/zoom.
    before = callback_post(app, "..position.figure", settings(), "candidate.value")
    values = settings()
    values[("reset", "n_clicks")] = 1
    after = callback_post(app, "..position.figure", values, "reset.n_clicks")
    for view in ("position", "embedding", "sky", "velocity"):
        assert before[view]["figure"]["layout"]["uirevision"] != after[view]["figure"]["layout"]["uirevision"]


@pytest.mark.parametrize("key,value,down,up", [
    ("min-seed", 0, True, False), ("min-seed", 1, False, True),
    ("max-size", None, True, False), ("cap", 1, True, False), ("cap", 5, False, False),
])
def test_stepper_boundary_states(saved, key, value, down, up):
    app = app_for(saved)
    response = callback_post(app, ".." + key + "-down.disabled", {(key, "value"): value}, key + ".value")
    assert response[key + "-down"]["disabled"] is down
    assert response[key + "-up"]["disabled"] is up


def test_empty_candidates_and_malformed_results(saved):
    stars = pd.read_csv(saved / "assigned_stars.csv", dtype={"source_id": "string"})
    stars["cluster_id"] = -1
    stars.to_csv(saved / "assigned_stars.csv", index=False)
    pd.DataFrame(columns=["cluster_id", "n_members"]).to_csv(saved / "candidate_catalog.csv", index=False)
    data = load_results(saved)
    display, _ = display_sample(data, [], show_noise=False)
    assert data.catalog.empty and display.empty
    assert make_view(data, display).data == ()
    app = app_for(saved)
    response = callback_post(app, "..position.figure", {**settings(), ("candidate", "value"): None, ("noise", "value"): []}, "noise.value")
    assert "No candidates" in response["details"]["children"]
    (saved / "summary.json").write_text("malformed")
    with pytest.raises(ValueError, match="Cannot load"):
        load_results(saved)
