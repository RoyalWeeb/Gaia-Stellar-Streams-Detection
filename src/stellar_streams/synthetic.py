"""Toy correlated phase-space trails; not simulated or observed named streams."""
from pathlib import Path
import numpy as np
import pandas as pd
import astropy.units as u
from astropy.coordinates import SkyCoord
from .preprocessing import galactic_frame


def make_demo(output, seed=42, field_stars=3600, members_per_stream=240):
    if field_stars < 120 or members_per_stream < 2:
        raise ValueError("Demo needs >=120 field stars and >=2 members per stream")
    rng = np.random.default_rng(seed)
    field = np.column_stack([rng.normal(0, 12, (field_stars, 2)),
                             rng.normal(0, 9, field_stars),
                             rng.normal(0, 140, (field_stars, 3))])
    parts = [field]
    truth = [-1] * field_stars
    centers = [[-10, 4, 7, 100, -110, 50], [6, -9, -8, -140, 70, -55],
               [4, 10, 10, 60, 160, -80]]
    directions = [[2.2, 1.0, .4, 12, 6, -4], [1, 2, -.5, -8, 10, 3],
                  [2, -1, .8, 6, -7, 4]]
    for label, (center, direction) in enumerate(zip(centers, directions)):
        t = rng.uniform(-1, 1, members_per_stream)
        noise = rng.normal(0, [.07, .07, .07, 1.2, 1.2, 1.2], (members_per_stream, 6))
        parts.append(np.asarray(center) + t[:, None] * direction + noise)
        truth.extend([label] * members_per_stream)
    phase = np.vstack(parts)
    c = SkyCoord(x=phase[:, 0] * u.kpc, y=phase[:, 1] * u.kpc, z=phase[:, 2] * u.kpc,
                 v_x=phase[:, 3] * u.km / u.s, v_y=phase[:, 4] * u.km / u.s,
                 v_z=phase[:, 5] * u.km / u.s, frame=galactic_frame()).icrs
    n = len(phase)
    true_parallax = 1 / c.distance.to_value(u.kpc)
    parallax_error = true_parallax * .02
    observed = true_parallax + rng.normal(0, parallax_error)
    data = pd.DataFrame({
        "source_id": [str(900000000000000000 + i) for i in range(n)],
        "ra": c.ra.deg, "dec": c.dec.deg, "parallax": observed,
        "parallax_error": parallax_error, "parallax_over_error": observed / parallax_error,
        "pmra": c.pm_ra_cosdec.to_value(u.mas/u.yr) + rng.normal(0, .01, n),
        "pmdec": c.pm_dec.to_value(u.mas/u.yr) + rng.normal(0, .01, n),
        "radial_velocity": c.radial_velocity.to_value(u.km/u.s) + rng.normal(0, .5, n),
        "radial_velocity_error": np.full(n, .5), "ruwe": rng.uniform(.8, 1.2, n),
        "phot_g_mean_mag": rng.uniform(10, 16, n)})
    data.loc[:39, "ruwe"] = 1.8
    data.loc[40:79, "parallax_error"] = data.loc[40:79, "parallax"] / 3
    data.loc[40:79, "parallax_over_error"] = 3
    data.loc[80:119, "radial_velocity_error"] = 8
    # Truth is a separate file, so preprocessing cannot leak labels into learning.
    truth_table = pd.DataFrame({"source_id": data.source_id, "truth_label": truth})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data.to_csv(output / "demo_gaia.csv", index=False)
    truth_table.to_csv(output / "demo_truth.csv", index=False)
    return data, truth_table
