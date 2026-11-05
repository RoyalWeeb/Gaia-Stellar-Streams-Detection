"""Isolated preview/fit process with atomic, pollable stage updates."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import traceback

from .config import Config
from .preprocessing import REQUIRED, read_chunks, load_halo_sample
from .reviews import atomic_json


def execute(directory, mode):
    directory = Path(directory)
    state = json.loads((directory / "job.json").read_text(encoding="utf-8"))
    config = Config(**state["config"])
    source = directory / state["input_file"]

    def update(**values):
        state.update(values)
        atomic_json(directory / "job.json", state)

    try:
        update(status="running", message="Checking input columns" if mode == "preview" else "Checking the previewed input")
        if mode == "preview":
            first = next(iter(read_chunks(source, config.chunk_size)), None)
            columns = list(first.columns) if first is not None else []
            preview = {"columns": columns, "missing_columns": sorted(set(REQUIRED) - set(columns)),
                       "sample_rows": json.loads(first.head(5).to_json(orient="records")) if first is not None else [],
                       "can_run": False}
            update(preview=preview)
            if preview["missing_columns"]:
                raise ValueError("Missing input columns: " + ", ".join(preview["missing_columns"]))

            def selection_progress(counts):
                update(message=f"Preview: {counts['raw_rows']:,} rows read; {counts['quality_rows']:,} pass quality; {counts['halo_rows']:,} pass the halo cut")
            selected, counts = load_halo_sample(source, replace(config, sampling="uniform"),
                                                progress=selection_progress, allow_empty=True)
            threshold = max(config.n_neighbors, config.min_cluster_size, config.min_samples, config.n_components + 1)
            reasons = []
            if counts["halo_rows"] > config.max_stars and config.sampling == "error":
                reasons.append(f"{counts['halo_rows']:,} eligible stars exceed the {config.max_stars:,} limit. Choose uniform sampling or a smaller input.")
            if len(selected) <= threshold:
                reasons.append(f"Only {len(selected):,} stars would be selected. More than {threshold:,} are required by these clustering settings. Adjust the cuts or cluster settings.")
            digest = hashlib.sha256()
            with source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            preview.update(counts=counts, can_run=not reasons, reasons=reasons,
                           input_sha256=digest.hexdigest(), input_bytes=source.stat().st_size,
                           selected_preview=json.loads(selected.head(5).to_json(orient="records")))
            update(status="ready", stage=1, preview=preview,
                   message="Preview ready. Start processing when you are satisfied with the selection." if not reasons else " ".join(reasons))
        else:
            # Verify that the copied input is still the file that was previewed.
            from .pipeline import file_hash, run_pipeline
            if file_hash(source) != state["preview"]["input_sha256"]:
                raise ValueError("The staged input changed after preview. Preview again.")
            summary = run_pipeline(source, directory / "results", config, data_kind=state["source"]["kind"],
                                   progress=lambda stage, message: update(stage=stage, message=message))
            # Retain the user's original filename alongside the staged file hash.
            summary["input_name"] = state["filename"]
            summary["dashboard_import"] = {"previewed": True, "job_id": state["id"]}
            atomic_json(directory / "results/summary.json", summary)
            update(status="completed", stage=5, selected_rows=summary["selection"]["selected_rows"],
                   n_candidates=summary["n_clusters"], message="Processing complete. Open the new results to review candidates.")
        return 0
    except Exception as exc:
        traceback.print_exc()
        update(status="failed", message=str(exc) or type(exc).__name__)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--mode", choices=["preview", "run"], required=True)
    args = parser.parse_args()
    raise SystemExit(execute(args.job, args.mode))
