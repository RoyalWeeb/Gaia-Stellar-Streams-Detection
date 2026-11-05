"""Paged, cached Gaia ADQL queries. No credentials are needed for public reads."""
from pathlib import Path
import json
import hashlib
import pandas as pd
from .config import Config
from .preprocessing import REQUIRED, normalize_ids


def make_query(last_id=0, page_size=10000, random_index_max=None, config=None):
    config = config or Config()
    if type(last_id) is not int or last_id < 0 or type(page_size) is not int or page_size < 1:
        raise ValueError("last_id and page_size must be valid nonnegative/positive integers")
    if random_index_max is not None and (type(random_index_max) is not int or random_index_max < 1):
        raise ValueError("random_index_max must be a positive integer")
    sample = "" if random_index_max is None else f"\n  AND random_index < {random_index_max}"
    return f"""SELECT TOP {page_size} {', '.join(REQUIRED)}, phot_g_mean_mag, random_index
FROM gaiadr3.gaia_source
WHERE source_id > {last_id}
  AND ra IS NOT NULL AND dec IS NOT NULL
  AND parallax > 0 AND parallax_error > 0
  AND pmra IS NOT NULL AND pmdec IS NOT NULL
  AND radial_velocity IS NOT NULL
  AND parallax_over_error > {config.parallax_snr_min}
  AND ruwe > 0 AND ruwe < {config.ruwe_max}
  AND radial_velocity_error > 0 AND radial_velocity_error < {config.rv_error_max}{sample}
ORDER BY source_id ASC"""


def fetch_gaia(output, page_size=10000, max_rows=100000, random_index_max=50000000,
               config=None, client=None):
    """Resume cached pages; max_rows=0 fetches the entire selected random-index subset.

    A positive max_rows limit can truncate sky-ordered IDs. The manifest marks this.
    The chunk cache is tied to the exact selection settings and checked on resume.
    """
    config = config or Config()
    if type(max_rows) is not int or max_rows < 0:
        raise ValueError("max_rows must be a nonnegative integer")
    make_query(0, page_size, random_index_max, config)  # validate before any I/O
    if client is None:
        from astroquery.gaia import Gaia
        client = Gaia
        client.ROW_LIMIT = -1
    output = Path(output)
    cache = output.parent / (output.stem + "_pages")
    cache.mkdir(parents=True, exist_ok=True)
    meta_path = cache / "manifest.json"
    settings = {"page_size": page_size, "max_rows": max_rows,
                "random_index_max": random_index_max,
                "quality": {k: config.to_dict()[k] for k in
                            ("ruwe_max", "parallax_snr_min", "rv_error_max")}}
    meta = {"settings": settings, "pages": [], "complete": False, "truncated": False}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta["settings"] != settings:
            raise ValueError("Query cache settings differ. Choose a new output filename.")
    last = 0
    total = 0
    for page in meta["pages"]:
        local = cache / page["file"]
        if hashlib.sha256(local.read_bytes()).hexdigest() != page["sha256"]:
            raise ValueError(f"Query cache changed: {local}")
        last, total = page["last_id"], total + page["rows"]
    while not meta["complete"] and not meta["truncated"]:
        size = min(page_size, max_rows - total) if max_rows else page_size
        if size == 0:
            meta["truncated"] = True
            break
        query = make_query(last, size, random_index_max, config)
        job = client.launch_job_async(query)
        result = job.get_results().to_pandas()
        if result.empty:
            meta["complete"] = True
        else:
            result["source_id"] = normalize_ids(result.source_id)
            ids = [int(v) for v in result.source_id]
            if len(ids) > size or min(ids) <= last or ids != sorted(set(ids)):
                raise ValueError("Archive page is oversized, repeated, or out of order")
            name = f"page_{len(meta['pages']):05d}.csv"
            file = cache / name
            result.to_csv(file, index=False)
            last = ids[-1]
            total += len(result)
            meta["pages"].append({"file": name, "rows": len(result), "last_id": last,
                                  "query": query, "job_id": str(job.jobid),
                                  "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
            if len(result) < size:
                meta["complete"] = True
            elif max_rows and total >= max_rows:
                meta["truncated"] = True
        temp = meta_path.with_suffix(".tmp")
        temp.write_text(json.dumps(meta, indent=2))
        temp.replace(meta_path)
    meta["total_rows"] = total
    meta["selection_note"] = ("Truncated in source_id order: not an unbiased full-sky sample."
                               if meta["truncated"] else "Complete selected random-index subset.")
    meta_path.write_text(json.dumps(meta, indent=2))
    # Stream cached bytes rather than loading the complete download in RAM.
    temp_output = output.with_suffix(output.suffix + ".tmp")
    with temp_output.open("w") as target:
        if not meta["pages"]:
            target.write(",".join(REQUIRED + ["phot_g_mean_mag", "random_index"]) + "\n")
        for index, page in enumerate(meta["pages"]):
            with (cache / page["file"]).open() as source:
                if index:
                    next(source)
                for line in source:
                    target.write(line)
    temp_output.replace(output)
    return meta
