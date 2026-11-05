import base64
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from stellar_streams.config import Config
from stellar_streams.dashboard_jobs import ImportManager, LOAD_FIELDS, import_config, source_descriptor
from stellar_streams.dashboard_worker import execute
from stellar_streams.preprocessing import REQUIRED
from stellar_streams.reviews import ReviewStore, atomic_json
from test_dashboard import saved, app_for, settings, callback_post


def catalogue(path, n=50, bad=4, disc=6):
    table = pd.DataFrame({"source_id": [str(900000000000000001 + i) for i in range(n)],
        "ra": [180.] * n, "dec": [85.] * n, "parallax": [.1] * n,
        "parallax_error": [.01] * n, "parallax_over_error": [10.] * n,
        "pmra": [1.] * n, "pmdec": [2.] * n, "radial_velocity": [50.] * n,
        "radial_velocity_error": [1.] * n, "ruwe": [1.] * n})
    table.loc[:bad-1, "ruwe"] = 2
    table.loc[bad:bad+disc-1, ["parallax", "parallax_error"]] = [10., .1]
    table.to_csv(path, index=False)
    return table


def prepared(tmp_path, config=None):
    source = tmp_path / "gaia.csv"
    catalogue(source)
    manager = ImportManager(tmp_path / "jobs", input_base=tmp_path)
    manager._launch = Mock()  # Execute the real worker synchronously below.
    config = config or replace(Config(), max_stars=100, min_cluster_size=5, n_neighbors=5,
                               min_samples=3, stability_runs=0)
    descriptor = source_descriptor("path", "gaia.csv", None, "gaia_dr3")
    key = manager.preview(descriptor, config)
    return manager, key, config, descriptor


def test_reviews_persist_run_bound_and_detect_stale_edits(saved):
    source_hash = (saved / "candidate_catalog.csv").read_bytes()
    store = ReviewStore(saved, [0, 1])
    assert store.get("0")["status"] == "Unreviewed"
    review = store.save("0", "Shortlisted", "Check the velocity gradient.\nKeep exact member IDs.", 0)
    assert review["revision"] == 1
    assert ReviewStore(saved, [0, 1]).get("0") == review
    assert (saved / "candidate_catalog.csv").read_bytes() == source_hash
    with pytest.raises(ValueError, match="another tab"):
        ReviewStore(saved, [0, 1]).save("0", "Rejected", "stale", 0)
    assert store.get("0")["status"] == "Shortlisted"
    with pytest.raises(ValueError, match="not part"):
        store.save("9", "Shortlisted", "", 0)
    (saved / "summary.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="not overwritten"):
        ReviewStore(saved, [0, 1]).save("0", "Rejected", "", 1)
    assert json.loads(store.path.read_text())["candidates"]["0"] == review


def test_corrupt_reviews_are_not_overwritten(saved):
    store = ReviewStore(saved, [0, 1])
    store.path.write_text("malformed")
    with pytest.raises(ValueError, match="not overwritten"):
        store.save("0", "Shortlisted", "", 0)
    assert store.path.read_text() == "malformed"


def test_review_callbacks_save_reload_filter_and_guard_wrong_selection(saved):
    app = app_for(saved)
    values = settings()
    loaded = callback_post(app, "..review-status.value", values, "candidate.value")
    target = loaded["review-target"]["data"]
    assert target["candidate"] == "0"
    values.update({("active-run", "data"): "saved", ("review-target", "data"): target,
                   ("review-status", "value"): "Shortlisted", ("review-notes", "value"): "Promising review example.",
                   ("save-review", "n_clicks"): 1})
    saved_review = callback_post(app, "..review-feedback.children", values, "save-review.n_clicks")
    assert "Saved review for candidate 0" in saved_review["review-feedback"]["children"]
    # A new app instance reads the on-disk review, not browser-only state.
    reopened = app_for(saved)
    loaded = callback_post(reopened, "..review-status.value", values, "candidate.value")
    assert loaded["review-notes"]["value"] == "Promising review example."
    values[("review-filter", "value")] = "Shortlisted"
    filtered = callback_post(reopened, "..candidates.data", values, "review-filter.value")
    assert [r["cluster_id"] for r in filtered["candidates"]["data"]] == [0]
    values[("candidate", "value")] = "1"
    rejected = callback_post(reopened, "..review-feedback.children", values, "save-review.n_clicks")
    assert "Wait for this candidate" in rejected["review-feedback"]["children"]
    assert ReviewStore(saved, [0, 1]).get("1")["status"] == "Unreviewed"


def test_preview_counts_and_start_requires_same_settings(tmp_path):
    manager, key, config, descriptor = prepared(tmp_path)
    assert execute(manager.directory(key), "preview") == 0
    state = manager.state(key)
    counts = state["preview"]["counts"]
    assert counts == {"raw_rows": 50, "quality_rows": 46, "halo_rows": 40,
                      "selected_rows": 40, "sampled": False, "quality_rejected": 4, "non_halo_rejected": 6}
    assert state["preview"]["can_run"]
    assert state["preview"]["selected_preview"][0]["source_id"] == "900000000000000011"
    assert state["preview"]["input_sha256"]
    with pytest.raises(ValueError, match="changed"):
        manager.start(key, replace(config, ruwe_max=1.3), descriptor)
    manager.start(key, config, descriptor)
    assert manager.state(key)["mode"] == "run"
    assert manager.state(key)["status"] == "queued"


def test_preview_limit_requires_explicit_sampling_and_handles_no_survivors(tmp_path):
    manager, key, config, descriptor = prepared(tmp_path, replace(Config(), max_stars=32,
        min_cluster_size=5, n_neighbors=5, min_samples=3, stability_runs=0))
    assert execute(manager.directory(key), "preview") == 0
    preview = manager.state(key)["preview"]
    assert preview["counts"]["halo_rows"] == 40
    assert preview["counts"]["selected_rows"] == 32
    assert not preview["can_run"]
    assert "exceed" in preview["reasons"][0]
    key2 = manager.preview(descriptor, replace(config, sampling="uniform"))
    assert execute(manager.directory(key2), "preview") == 0
    assert manager.state(key2)["preview"]["can_run"]
    config_empty = replace(config, halo_z_min_kpc=100)
    key3 = manager.preview(descriptor, config_empty)
    assert execute(manager.directory(key3), "preview") == 0
    preview = manager.state(key3)["preview"]
    assert preview["counts"]["selected_rows"] == 0
    assert not preview["can_run"]


def test_upload_missing_columns_bad_ids_and_untrusted_paths(tmp_path):
    manager = ImportManager(tmp_path / "jobs")
    manager._launch = Mock()
    config = Config()
    descriptor = source_descriptor("upload", None, {"filename": "my.csv"}, "gaia_dr3")
    key = manager.preview(descriptor, config, "data:text/csv;base64," + base64.b64encode(b"ra,dec\n1,2\n").decode(), "../../my.csv")
    assert manager.state(key)["filename"] == "my.csv"
    assert execute(manager.directory(key), "preview") == 1
    assert "source_id" in manager.state(key)["preview"]["missing_columns"]
    assert not (tmp_path / "my.csv").exists()
    with pytest.raises(ValueError, match="Unknown"):
        manager.directory("../../escape")
    with pytest.raises(ValueError, match="Choose a .csv"):
        manager.preview(descriptor, config, "data:text/plain;base64,YQ==", "input.exe")
    with pytest.raises(ValueError, match="choose it again"):
        manager.preview(descriptor, config, "invalid", "input.csv")
    source = tmp_path / "bad.csv"
    data = catalogue(source)
    data.loc[10, "source_id"] = "9e17"
    data.to_csv(source, index=False)
    key2 = manager.preview(source_descriptor("path", str(source), None, "gaia_dr3"), config)
    assert execute(manager.directory(key2), "preview") == 1
    assert "unsigned decimal" in manager.state(key2)["message"]


def test_changed_staged_file_cannot_be_fitted(tmp_path):
    manager, key, config, descriptor = prepared(tmp_path)
    assert execute(manager.directory(key), "preview") == 0
    state = manager.state(key)
    (manager.directory(key) / state["input_file"]).write_text("changed")
    manager.start(key, config, descriptor)
    assert execute(manager.directory(key), "run") == 1
    assert "changed after preview" in manager.state(key)["message"]
    assert not (manager.directory(key) / "results").exists()


def test_switching_saved_runs_isolates_reviews_and_updates_counts(saved, tmp_path):
    app = app_for(saved)
    key = "a" * 32
    directory = app.import_manager.directory(key)
    directory.mkdir()
    import shutil
    shutil.copytree(saved, directory / "results")
    atomic_json(directory / "job.json", {"id": key, "status": "completed", "filename": "second.csv"})
    ReviewStore(saved, [0, 1]).save("0", "Rejected", "Only the first run.", 0)
    values = {("run-select", "value"): key}
    selected = callback_post(app, "..active-run.data", values, "run-select.value")
    assert selected["active-run"]["data"] == key
    assert selected["run-settings"]["data"]["total"] == 8
    values = {**settings(), ("active-run", "data"): key}
    review = callback_post(app, "..review-status.value", values, "active-run.data")
    assert review["review-status"]["value"] == "Unreviewed"
    assert review["review-notes"]["value"] == ""


def test_guided_config_rejects_fractional_counts_and_excessive_jobs():
    values = {s[0]: getattr(Config(), s[0]) for s in LOAD_FIELDS}
    with pytest.raises(ValueError, match="whole number"):
        import_config({**values, "n_neighbors": 3.5})
    with pytest.raises(ValueError, match="outside"):
        import_config({**values, "stability_runs": 200})
    with pytest.raises(ValueError, match="outside"):
        import_config({**values, "max_stars": 2000000})


def test_guided_callbacks_preview_and_block_stale_settings(saved, tmp_path):
    app = app_for(saved)
    app.import_manager._launch = Mock()
    source = tmp_path / "callback_gaia.csv"
    catalogue(source)
    config = replace(Config(), max_stars=100, min_cluster_size=5, n_neighbors=5,
                     min_samples=3, stability_runs=0)
    values = {("input-mode", "value"): "path", ("input-path", "value"): str(source),
              ("input-kind", "value"): "gaia_dr3", ("load-sampling", "value"): "error",
              ("preview-data", "n_clicks"): 1}
    values.update({("load-" + field[0], "value"): getattr(config, field[0]) for field in LOAD_FIELDS})
    created = callback_post(app, "..import-job.data", values, "preview-data.n_clicks")
    key = created["import-job"]["data"]
    assert execute(app.import_manager.directory(key), "preview") == 0
    values[("import-job", "data")] = key
    ready = callback_post(app, "..job-progress.value", values, "import-job.data")
    assert ready["start-processing"]["disabled"] is False
    assert "callback_gaia.csv" in str(ready["preview-summary"])
    values[("load-ruwe_max", "value")] = 1.3
    stale = callback_post(app, "..job-progress.value", values, "load-ruwe_max.value")
    assert stale["start-processing"]["disabled"] is True
    assert "changed" in stale["job-stage"]["children"]
    blocked = callback_post(app, "..import-job.data", values, "start-processing.n_clicks")
    assert "changed" in blocked["import-message"]["children"]
    assert app.import_manager.state(key)["status"] == "ready"
