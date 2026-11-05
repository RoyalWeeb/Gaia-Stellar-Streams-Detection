"""Run-bound, atomic reviewer decisions; never modifies analytical CSVs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading

REVIEW_STATUSES = ("Unreviewed", "Shortlisted", "Needs investigation", "Rejected")
_locks = {}
_locks_guard = threading.Lock()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".pending-", suffix=".json", delete=False) as stream:
            name = stream.name
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


class ReviewStore:
    def __init__(self, results, candidate_ids):
        self.path = Path(results).resolve() / "candidate_reviews.json"
        self.candidates = {str(int(value)) for value in candidate_ids}
        digest = hashlib.sha256()
        for name in ("summary.json", "candidate_catalog.csv"):
            digest.update((self.path.parent / name).read_bytes())
        self.fingerprint = digest.hexdigest()
        with _locks_guard:
            self.lock = _locks.setdefault(str(self.path), threading.Lock())

    def _read(self):
        if not self.path.exists():
            return {"schema_version": 1, "run_fingerprint": self.fingerprint, "candidates": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (value.get("schema_version") != 1 or value.get("run_fingerprint") != self.fingerprint
                    or not isinstance(value.get("candidates"), dict)):
                raise ValueError("Review file does not match this saved run")
            for key, record in value["candidates"].items():
                if (key not in self.candidates or not isinstance(record, dict)
                        or record.get("status") not in REVIEW_STATUSES
                        or not isinstance(record.get("notes"), str)
                        or type(record.get("revision")) is not int):
                    raise ValueError("Review file contains an invalid candidate record")
            return value
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"Cannot read saved reviews: {exc}. The file was not overwritten.") from exc

    def all(self):
        with self.lock:
            return self._read()["candidates"]

    def get(self, candidate):
        key = str(candidate)
        if key not in self.candidates:
            raise ValueError("Select a candidate in this run before reviewing it")
        return self.all().get(key, {"status": "Unreviewed", "notes": "", "updated_at": None, "revision": 0})

    def save(self, candidate, status, notes, expected_revision):
        key = str(candidate)
        if key not in self.candidates:
            raise ValueError("This candidate is not part of the loaded run")
        if status not in REVIEW_STATUSES:
            raise ValueError("Choose one of the available review statuses")
        if not isinstance(notes, str) or len(notes) > 10000:
            raise ValueError("Review notes must be text of at most 10,000 characters")
        with self.lock:
            value = self._read()
            previous = value["candidates"].get(key, {})
            if expected_revision != previous.get("revision", 0):
                raise ValueError("This review changed in another tab. Reselect the candidate to load the latest notes before saving.")
            record = {"status": status, "notes": notes,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "revision": previous.get("revision", 0) + 1}
            value["candidates"][key] = record
            atomic_json(self.path, value)
            return record
