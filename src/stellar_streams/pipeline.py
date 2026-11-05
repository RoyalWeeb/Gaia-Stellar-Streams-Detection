from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import platform
import time
from importlib.metadata import version, PackageNotFoundError
from .config import Config
from .preprocessing import load_halo_sample, FRAME
from .clustering import fit_clusters
from .validation import evaluate_toy_truth
from .plots import make_plots


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pipeline(input_path, output_path, config=None, truth=None, data_kind="user_supplied", progress=None):
    config = config or Config()
    if data_kind not in ("synthetic_toy", "user_supplied", "gaia_dr3"):
        raise ValueError("Unknown data_kind")
    if truth is not None and data_kind != "synthetic_toy":
        raise ValueError("Toy truth evaluation requires data_kind=synthetic_toy")
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Output folder must be empty; choose a new folder to preserve earlier runs")
    start = time.perf_counter()
    def report(stage, message):
        if progress:
            progress(stage, message)
    report(1, "Applying measurement cuts and converting coordinates")
    print("[1/5] Applying quality cuts and converting to Galactocentric phase space", flush=True)
    sample, selection = load_halo_sample(input_path, config, progress=(
        lambda counts: report(1, f"Read {counts['raw_rows']:,} rows; {counts['halo_rows']:,} pass quality and halo cuts")
    ) if progress else None)
    print(f"[2/5] Embedding and clustering {len(sample):,} selected stars", flush=True)
    assigned, catalog, stability, diagnostics = fit_clusters(sample, config, progress=(
        lambda message: report(2, message)) if progress else None)
    report(3, "Saving full memberships and candidate diagnostics")
    print("[3/5] Preparing candidate diagnostics and optional toy evaluation", flush=True)
    if truth is not None:
        evaluation = evaluate_toy_truth(assigned, truth)
        (output / "toy_evaluation.json").write_text(json.dumps(evaluation, indent=2))
    assigned.to_csv(output / "assigned_stars.csv", index=False)
    catalog.to_csv(output / "candidate_catalog.csv", index=False)
    stability.to_csv(output / "seed_stability.csv", index=False)
    packages = {}
    for name in ("numpy", "pandas", "scipy", "scikit-learn", "astropy", "astroquery", "umap-learn", "hdbscan", "matplotlib", "plotly"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not installed"
    summary = {"project_version": "1.0.0", "utc_time": datetime.now(timezone.utc).isoformat(),
               "data_kind": data_kind, "input_name": Path(input_path).name,
               "input_sha256": file_hash(input_path), "selection": selection,
               "config": config.to_dict(), "galactocentric_frame": FRAME,
               "python": platform.python_version(), "packages": packages,
               **diagnostics,
               "scientific_status": "Candidate generation only; no confirmed stream discoveries.",
               "distance_method": "Uncorrected inverse positive parallax in mas gives distance in kpc.",
               "uncertainty_note": "Quality filtering only. No correlated astrometric-error propagation or parallax zero-point correction."}
    print("[4/5] Saving plots and interactive offline explorer", flush=True)
    report(4, "Building static plots and the offline explorer")
    make_plots(assigned, catalog, summary, output, config)
    summary["elapsed_seconds"] = round(time.perf_counter() - start, 2)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    report(5, f"Complete: {len(catalog):,} candidates from {len(assigned):,} selected stars")
    print(f"[5/5] Done: {len(catalog)} candidates; outputs in {output}", flush=True)
    return summary
