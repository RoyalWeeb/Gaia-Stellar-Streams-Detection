from dataclasses import replace
import json
import numpy as np
import pandas as pd
import pytest
from astropy.table import Table
from stellar_streams.config import Config
from stellar_streams.preprocessing import quality_filter, to_phase_space, normalize_ids, load_halo_sample, FEATURES
from stellar_streams.synthetic import make_demo
from stellar_streams.archive import make_query, fetch_gaia
from stellar_streams.clustering import best_jaccard


@pytest.fixture
def observations(tmp_path):
    data, truth = make_demo(tmp_path, field_stars=200, members_per_stream=20)
    return data, truth


@pytest.mark.parametrize("kwargs", [{"min_samples": 0}, {"n_components": 6}, {"sampling": "silent"},
                                   {"velocity_weight": -1}, {"stability_runs": -1}, {"seed": 2.5},
                                   {"cluster_selection_method": "unknown"}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_quality_cuts_and_halo(observations):
    data, _ = observations
    clean = quality_filter(data, Config())
    assert len(clean) == len(data) - 120
    assert np.isfinite(to_phase_space(clean)[FEATURES]).all().all()
    assert len(to_phase_space(clean).loc[lambda d: d.z_kpc.abs() > 3]) >= 60


def test_strict_boundaries_and_missing_data(observations):
    row = observations[0].iloc[150:151].copy()
    assert len(quality_filter(row, Config())) == 1
    for key, value in [("ruwe", 1.4), ("parallax_over_error", 5), ("radial_velocity_error", 5),
                       ("parallax", 0), ("pmra", np.nan), ("ra", 360), ("dec", 91)]:
        bad = row.copy()
        bad[key] = value
        assert quality_filter(bad, Config()).empty


def test_ids_are_exact():
    values = pd.Series(["900000000000000001", "900000000000000002"], dtype="string")
    assert list(normalize_ids(values)) == list(values)
    with pytest.raises(ValueError):
        normalize_ids(pd.Series([9e17]))


@pytest.mark.parametrize("arguments", [
    ["compare", "--help"],
    ["demo", "--compare"],
    ["run", "--input", "unused.csv", "--output", "unused", "--reference", "unused.csv"],
    ["dashboard", "--results", "unused", "--comparison", "unused"],
    ["dashboard", "--results", "unused", "--reference", "unused.csv"],
])
def test_removed_workflows_are_not_cli_options(monkeypatch, arguments):
    from stellar_streams.cli import main
    monkeypatch.setattr("sys.argv", ["gaia-streams", *arguments])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_synthetic_frame_roundtrip(tmp_path):
    # Noiseless ICRS -> Galactocentric -> ICRS -> Galactocentric should retain velocities.
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from stellar_streams.preprocessing import galactic_frame
    original = SkyCoord(x=-10*u.kpc, y=4*u.kpc, z=7*u.kpc,
                        v_x=100*u.km/u.s, v_y=-110*u.km/u.s, v_z=50*u.km/u.s,
                        frame=galactic_frame())
    c = original.icrs
    df = pd.DataFrame({"ra": [c.ra.deg], "dec": [c.dec.deg], "parallax": [1/c.distance.to_value(u.kpc)],
                       "pmra": [c.pm_ra_cosdec.to_value(u.mas/u.yr)], "pmdec": [c.pm_dec.to_value(u.mas/u.yr)],
                       "radial_velocity": [c.radial_velocity.to_value(u.km/u.s)]})
    actual = to_phase_space(df)[FEATURES].to_numpy()[0]
    np.testing.assert_allclose(actual, [-10, 4, 7, 100, -110, 50], atol=1e-9)


def test_sampling_cap_is_explicit(tmp_path):
    make_demo(tmp_path, field_stars=500, members_per_stream=60)
    config = replace(Config(), max_stars=80, chunk_size=73, min_cluster_size=20)
    with pytest.raises(ValueError, match="exceeds"):
        load_halo_sample(tmp_path / "demo_gaia.csv", config)
    selected, stats = load_halo_sample(tmp_path / "demo_gaia.csv", replace(config, sampling="uniform"))
    again, _ = load_halo_sample(tmp_path / "demo_gaia.csv", replace(config, sampling="uniform"))
    assert len(selected) == 80 and stats["sampled"]
    assert list(selected.source_id) == list(again.source_id)
    assert (selected.z_kpc.abs() > 3).all()


def test_query_and_paged_resume(tmp_path):
    class Job:
        jobid = "mock-job"
        def __init__(self, ids):
            self.ids = ids
        def get_results(self):
            return Table({"source_id": self.ids})
    class Client:
        calls = []
        def launch_job_async(self, query):
            self.calls.append(query)
            return Job([900000000000000001, 900000000000000002] if len(self.calls) == 1 else [])
    client = Client()
    output = tmp_path / "gaia.csv"
    first = fetch_gaia(output, page_size=2, max_rows=0, client=client)
    assert first["complete"] and first["total_rows"] == 2
    assert "source_id > 900000000000000002" in client.calls[1]
    assert "ORDER BY source_id ASC" in client.calls[0]
    second = fetch_gaia(output, page_size=2, max_rows=0, client=client)
    assert len(client.calls) == 2 and second["total_rows"] == 2
    values = pd.read_csv(output, dtype="string")
    assert values.source_id.iloc[0] == "900000000000000001"


def test_membership_agreement_is_label_permutation_invariant():
    assert best_jaccard(np.array([0, 0, 1, 1, -1]), np.array([3, 3, 4, 4, -1])) == {0: 1.0, 1: 1.0}


def test_truncation_and_cache_integrity(tmp_path):
    class Job:
        jobid = "mock"
        def get_results(self):
            return Table({"source_id": [10, 20]})
    class Client:
        def launch_job_async(self, query):
            return Job()
    output = tmp_path / "gaia.csv"
    meta = fetch_gaia(output, page_size=2, max_rows=2, client=Client())
    assert meta["truncated"] and not meta["complete"]
    with pytest.raises(ValueError, match="settings"):
        fetch_gaia(output, page_size=2, max_rows=3, client=Client())
    (tmp_path / "gaia_pages/page_00000.csv").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        fetch_gaia(output, page_size=2, max_rows=2, client=Client())


def test_query_injection_rejected():
    with pytest.raises(ValueError):
        make_query(last_id="0 OR 1=1")


def test_no_clusters_is_valid():
    from stellar_streams.clustering import fit_clusters
    rng = np.random.default_rng(8)
    data = pd.DataFrame(rng.normal(size=(200, 6)), columns=FEATURES)
    data["source_id"] = pd.Series([str(i) for i in range(200)], dtype="string")
    config = replace(Config(), n_neighbors=10, min_cluster_size=190, stability_runs=0)
    assigned, catalog, stability, summary = fit_clusters(data, config)
    assert (assigned.cluster_id == -1).all()
    assert catalog.empty and "original_6d_supported" in catalog
    assert stability.empty and summary["n_clusters"] == 0
