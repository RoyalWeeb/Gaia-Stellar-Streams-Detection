"""Managed local-file imports and background workers for the dashboard."""
import base64
import binascii
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import threading
import uuid

from .config import Config
from .reviews import atomic_json

EXTENSIONS = {".csv", ".vot", ".votable", ".xml"}
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
LOAD_FIELDS = (
    ("ruwe_max", "Maximum RUWE", .01, None, .1),
    ("parallax_snr_min", "Minimum parallax signal to noise", .01, None, 1),
    ("rv_error_max", "Maximum radial-velocity error (km/s)", .01, None, 1),
    ("halo_z_min_kpc", "Minimum absolute Galactic z (kpc)", 0, None, .5),
    ("max_stars", "Selected-star limit", 32, 100000, 1),
    ("n_neighbors", "UMAP neighbours", 2, 200, 1),
    ("min_cluster_size", "Minimum cluster size", 2, 100000, 1),
    ("min_samples", "HDBSCAN minimum samples", 1, 100000, 1),
    ("n_components", "Embedding dimensions (2 or 3)", 2, 3, 1),
    ("stability_runs", "Extra seed checks", 0, 5, 1),
    ("seed", "Random seed", 0, 4294967295, 1),
)
INTEGER_FIELDS = {"max_stars", "n_neighbors", "min_cluster_size", "min_samples", "n_components", "stability_runs", "seed"}


def import_config(values, sampling="error"):
    values = dict(values)
    for key, _, lower, upper, _ in LOAD_FIELDS:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Enter a number for {key.replace('_', ' ')}")
        if key in INTEGER_FIELDS:
            if not float(value).is_integer():
                raise ValueError(f"{key.replace('_', ' ')} must be a whole number")
            values[key] = int(value)
        if value < lower or (upper is not None and value > upper):
            raise ValueError(f"{key.replace('_', ' ')} is outside the available range")
    return replace(Config(), **values, sampling=sampling)


def source_descriptor(mode, path, signature, kind):
    if kind not in ("gaia_dr3", "user_supplied"):
        raise ValueError("Choose the data origin")
    if mode == "path":
        return {"mode": mode, "path": str(path or "").strip(), "kind": kind}
    if mode == "upload":
        return {"mode": mode, "upload": signature, "kind": kind}
    raise ValueError("Choose a local file or a local path")


class ImportManager:
    def __init__(self, workspace, input_base=None):
        self.root = Path(workspace).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.input_base = Path(input_base or Path.cwd()).resolve()
        self.lock = threading.Lock()
        self.process = None

    def directory(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ValueError("Unknown data-processing job")
        return self.root / key

    def state(self, key):
        path = self.directory(key) / "job.json"
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("id") != key:
                raise ValueError("Job identifier mismatch")
            return state
        except (OSError, ValueError, AttributeError) as exc:
            raise ValueError("Cannot read this data-processing job; preview the file again") from exc

    def _available(self):
        if self.process is not None and self.process.poll() is None:
            raise ValueError("A data job is already running. Wait for it to finish before starting another.")

    def _launch(self, directory, mode):
        env = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with (directory / "worker.log").open("a", encoding="utf-8") as log:
            self.process = subprocess.Popen([sys.executable, "-m", "stellar_streams.dashboard_worker",
                "--job", str(directory), "--mode", mode], cwd=self.input_base, env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        process = self.process

        def monitor():
            code = process.wait()
            if code:
                try:
                    state = self.state(directory.name)
                    if state["status"] not in ("failed", "completed", "ready"):
                        state.update(status="failed", message="Processing stopped unexpectedly. Preview again to retry; earlier results are preserved.")
                        atomic_json(directory / "job.json", state)
                except ValueError:
                    pass
        threading.Thread(target=monitor, daemon=True).start()

    def preview(self, descriptor, config, contents=None, filename=None):
        with self.lock:
            self._available()
            if descriptor["mode"] == "path":
                if not descriptor["path"]:
                    raise ValueError("Enter the path to a local CSV or VOTable")
                source = Path(descriptor["path"]).expanduser()
                source = (self.input_base / source).resolve() if not source.is_absolute() else source.resolve()
                if not source.is_file():
                    raise ValueError("The local file was not found. Check its path.")
                filename = source.name
            else:
                source = None
                if not contents or not filename:
                    raise ValueError("Choose a CSV or VOTable before previewing")
                if not isinstance(contents, str) or len(contents) > MAX_UPLOAD_BYTES * 4 // 3 + 1024:
                    raise ValueError("Files larger than 64 MiB must use the local-path option")
                try:
                    header, encoded = contents.split(",", 1)
                    if not header.startswith("data:") or ";base64" not in header:
                        raise ValueError("Invalid file encoding")
                    uploaded = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ValueError("Cannot read the chosen file; choose it again") from exc
                if len(uploaded) > MAX_UPLOAD_BYTES:
                    raise ValueError("Files larger than 64 MiB must use the local-path option")
            filename = PureWindowsPath(str(filename)).name
            if Path(filename).suffix.lower() not in EXTENSIONS:
                raise ValueError("Choose a .csv, .vot, .votable or .xml Gaia catalogue")
            directory = self.directory(uuid.uuid4().hex)
            directory.mkdir()
            target = directory / ("input" + Path(filename).suffix.lower())
            if source:
                shutil.copyfile(source, target)
            else:
                target.write_bytes(uploaded)
            state = {"id": directory.name, "status": "queued", "mode": "preview", "stage": 0,
                     "created_at": datetime.now(timezone.utc).isoformat(), "filename": filename,
                     "source": descriptor, "config": config.to_dict(), "input_file": target.name,
                     "message": "Preparing a full-file selection preview", "preview": None}
            atomic_json(directory / "job.json", state)
            try:
                self._launch(directory, "preview")
            except OSError as exc:
                state.update(status="failed", message="Could not start the local processing worker")
                atomic_json(directory / "job.json", state)
                raise ValueError(state["message"]) from exc
            return directory.name

    def start(self, key, config, descriptor):
        with self.lock:
            self._available()
            state = self.state(key)
            if state["status"] != "ready" or not (state.get("preview") or {}).get("can_run"):
                raise ValueError("Preview a valid file before starting processing")
            if state["config"] != config.to_dict() or state["source"] != descriptor:
                raise ValueError("The file or settings changed. Preview again before starting.")
            state.update(status="queued", mode="run", stage=1, message="Starting candidate processing")
            directory = self.directory(key)
            atomic_json(directory / "job.json", state)
            try:
                self._launch(directory, "run")
            except OSError as exc:
                state.update(status="failed", message="Could not start the local processing worker")
                atomic_json(directory / "job.json", state)
                raise ValueError(state["message"]) from exc

    def completed(self):
        result = []
        for path in sorted(self.root.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                state = self.state(path.parent.name)
                if state["status"] == "completed" and (path.parent / "results/summary.json").is_file():
                    result.append(state)
            except ValueError:
                continue
        return result

    def result_path(self, key):
        if self.state(key)["status"] != "completed":
            raise ValueError("Results are not ready yet")
        return self.directory(key) / "results"
