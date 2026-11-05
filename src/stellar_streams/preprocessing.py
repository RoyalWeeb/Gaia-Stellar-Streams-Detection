"""Chunked CSV/VOTable ingestion and explicit Astropy frame transforms."""
from pathlib import Path
import numpy as np
import pandas as pd
import astropy.units as u
from astropy.coordinates import SkyCoord, Galactocentric, CartesianDifferential
from astropy.table import Table

OBSERVABLES = ["ra", "dec", "parallax", "pmra", "pmdec", "radial_velocity"]
QUALITY = ["parallax_error", "parallax_over_error", "ruwe", "radial_velocity_error"]
REQUIRED = ["source_id"] + OBSERVABLES + QUALITY
FEATURES = ["x_kpc", "y_kpc", "z_kpc", "vx_kms", "vy_kms", "vz_kms"]
FRAME = {"galcen_distance_kpc": 8.122, "z_sun_pc": 20.8,
         "solar_velocity_kms": [12.9, 245.6, 7.78],
         "galcen_ra_deg": 266.4051, "galcen_dec_deg": -28.936175, "roll_deg": 0.0}


def galactic_frame():
    return Galactocentric(
        galcen_coord=SkyCoord(ra=FRAME["galcen_ra_deg"] * u.deg,
                             dec=FRAME["galcen_dec_deg"] * u.deg, frame="icrs"),
        galcen_distance=FRAME["galcen_distance_kpc"] * u.kpc,
        z_sun=FRAME["z_sun_pc"] * u.pc,
        galcen_v_sun=CartesianDifferential(FRAME["solar_velocity_kms"] * u.km / u.s),
        roll=0 * u.deg)


def normalize_ids(series):
    # Never convert Gaia IDs through float64 (IDs exceed 2**53).
    if pd.api.types.is_float_dtype(series.dtype):
        raise ValueError("source_id was read as float; reload it as string or integer")
    s = series.astype("string").str.strip()
    valid = s.str.fullmatch(r"[0-9]+", na=False)
    if not valid.all():
        raise ValueError("source_id must contain non-null unsigned decimal identifiers")
    return s.map(lambda x: str(int(x))).astype("string")


def quality_filter(df, config):
    missing = set(REQUIRED) - set(df)
    if missing:
        raise ValueError(f"Missing input columns: {sorted(missing)}")
    out = df.copy()
    out["source_id"] = normalize_ids(out["source_id"])
    for key in OBSERVABLES + QUALITY:
        out[key] = pd.to_numeric(out[key], errors="coerce")
    good = np.isfinite(out[OBSERVABLES + QUALITY]).all(axis=1)
    good &= out.ra.between(0, 360, inclusive="left") & out.dec.between(-90, 90)
    good &= (out.parallax > 0) & (out.parallax_error > 0)
    good &= (out.ruwe > 0) & (out.ruwe < config.ruwe_max)
    # Both the supplied statistic and the actual ratio must pass.
    good &= (out.parallax_over_error > config.parallax_snr_min)
    good &= (out.parallax / out.parallax_error > config.parallax_snr_min)
    good &= (out.radial_velocity_error > 0) & (out.radial_velocity_error < config.rv_error_max)
    return out.loc[good].copy()


def to_phase_space(df):
    if df.empty:
        return df.assign(**{key: pd.Series(dtype=float) for key in FEATURES})
    c = SkyCoord(ra=df.ra.to_numpy() * u.deg, dec=df.dec.to_numpy() * u.deg,
                 distance=(1.0 / df.parallax.to_numpy()) * u.kpc,
                 pm_ra_cosdec=df.pmra.to_numpy() * u.mas / u.yr,
                 pm_dec=df.pmdec.to_numpy() * u.mas / u.yr,
                 radial_velocity=df.radial_velocity.to_numpy() * u.km / u.s,
                 frame="icrs").transform_to(galactic_frame())
    out = df.copy()
    for key, values in zip(FEATURES, list(c.cartesian.xyz.to_value(u.kpc)) +
                           list(c.velocity.d_xyz.to_value(u.km / u.s))):
        out[key] = values
    return out


def read_chunks(path, chunk_size):
    path = Path(path)
    if path.suffix.lower() in (".xml", ".vot", ".votable"):
        # VOTable parsing is eager. Convert large VOTables to CSV first.
        table = Table.read(path, format="votable").to_pandas()
        for start in range(0, len(table), chunk_size):
            yield table.iloc[start:start + chunk_size].copy()
    else:
        yield from pd.read_csv(path, dtype={"source_id": "string"}, chunksize=chunk_size)


def load_halo_sample(path, config, progress=None, allow_empty=False):
    stats = {"raw_rows": 0, "quality_rows": 0, "halo_rows": 0}
    rng = np.random.default_rng(config.seed)
    kept = None
    for chunk in read_chunks(path, config.chunk_size):
        stats["raw_rows"] += len(chunk)
        clean = quality_filter(chunk, config)
        stats["quality_rows"] += len(clean)
        phase = to_phase_space(clean)
        phase = phase.loc[phase.z_kpc.abs() > config.halo_z_min_kpc].copy()
        stats["halo_rows"] += len(phase)
        if config.sampling == "error" and stats["halo_rows"] > config.max_stars:
            raise ValueError(f"Halo sample exceeds max_stars={config.max_stars}. "
                             "Use a smaller input, raise the cap, or select sampling: uniform.")
        phase["_sample_key"] = rng.random(len(phase))
        kept = phase if kept is None else pd.concat([kept, phase], ignore_index=True)
        if len(kept) > config.max_stars:
            kept = kept.nsmallest(config.max_stars, "_sample_key")
        if progress:
            progress(dict(stats))
    if (kept is None or kept.empty) and not allow_empty:
        raise ValueError("No stars survived quality and halo cuts")
    if kept is None:
        kept = pd.DataFrame(columns=REQUIRED + FEATURES + ["_sample_key"])
    kept = kept.drop(columns="_sample_key").reset_index(drop=True)
    if kept.source_id.duplicated().any():
        raise ValueError("Duplicate source_id in selected sample; remove overlapping input rows")
    stats["selected_rows"] = len(kept)
    stats["sampled"] = stats["halo_rows"] > len(kept)
    stats["quality_rejected"] = stats["raw_rows"] - stats["quality_rows"]
    stats["non_halo_rejected"] = stats["quality_rows"] - stats["halo_rows"]
    return kept, stats
