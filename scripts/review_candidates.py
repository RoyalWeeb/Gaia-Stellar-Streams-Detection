"""Audit an existing run without refitting; all cuts are descriptive triage only."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def review(run, output):
    output.mkdir(parents=True, exist_ok=True)
    stars = pd.read_csv(run / "assigned_stars.csv", dtype={"source_id": "string"})
    catalog = pd.read_csv(run / "candidate_catalog.csv")
    stability = pd.read_csv(run / "seed_stability.csv")
    summary = json.loads((run / "summary.json").read_text())
    if stars.source_id.duplicated().any():
        raise ValueError("Duplicate assigned source IDs")
    actual = stars.loc[stars.cluster_id >= 0].groupby("cluster_id").size()
    expected = catalog.set_index("cluster_id").n_members
    pd.testing.assert_series_equal(actual.sort_index(), expected.sort_index(), check_names=False)
    seed_groups = stability.groupby("cluster_id").best_membership_jaccard
    catalog["seed_jaccard_min"] = catalog.cluster_id.map(seed_groups.min())
    catalog["seed_runs_available"] = catalog.cluster_id.map(seed_groups.count()).fillna(0).astype(int)
    expected_runs = summary["config"]["stability_runs"]
    complete = catalog.seed_runs_available.eq(expected_runs) & (expected_runs > 0)
    catalog["review_tier"] = "defer"
    stable = complete & catalog.seed_jaccard_min.ge(.7)
    physical = catalog.position_elongation.ge(2) & catalog.velocity_dispersion_3d_kms.le(60)
    catalog.loc[stable & physical, "review_tier"] = "secondary"
    catalog.loc[catalog.direct_6d_best_jaccard.ge(.1), "review_tier"] = "secondary"
    catalog.loc[stable & catalog.direct_6d_best_jaccard.ge(.5), "review_tier"] = "priority"
    diagnostics = []
    for cid, group in stars.loc[stars.cluster_id >= 0].groupby("cluster_id"):
        diagnostics.append({"cluster_id": cid,
            "fraction_within_0p5_kpc_of_z_cut": (group.z_kpc.abs() < summary["config"]["halo_z_min_kpc"] + .5).mean(),
            "median_parallax_snr": group.parallax_over_error.median(),
            "median_distance_kpc": (1 / group.parallax).median(),
            "distance_p10_kpc": (1 / group.parallax).quantile(.1),
            "distance_p90_kpc": (1 / group.parallax).quantile(.9),
            "median_rv_error_kms": group.radial_velocity_error.median()})
    catalog = catalog.merge(pd.DataFrame(diagnostics), on="cluster_id", validate="one_to_one")
    catalog["review_flags"] = [
        ";".join(flag for condition, flag in [
            (r.seed_runs_available != expected_runs or expected_runs == 0, "seed_evidence_incomplete"),
            (r.seed_jaccard_min < .7, "seed_sensitive"),
            (r.direct_6d_best_jaccard < .5, "weak_direct_6d_agreement"),
            (r.fraction_within_0p5_kpc_of_z_cut >= .5, "near_selection_boundary"),
            (r.velocity_dispersion_3d_kms > 60, "broad_raw_velocity_distribution")]
            if condition) for r in catalog.itertuples()]
    catalog["tier_order"] = catalog.review_tier.map({"priority": 0, "secondary": 1, "defer": 2})
    catalog = catalog.sort_values(["tier_order", "direct_6d_best_jaccard", "seed_jaccard_min", "cluster_id"],
                                  ascending=[True, False, False, True]).drop(columns="tier_order")
    catalog.insert(0, "review_rank", range(1, len(catalog) + 1))
    catalog.to_csv(output / "reviewed_candidate_catalog.csv", index=False)
    shortlist = catalog.loc[catalog.review_tier != "defer"]
    shortlist.to_csv(output / "shortlist.csv", index=False)
    stars.loc[stars.cluster_id.isin(shortlist.cluster_id)].to_csv(output / "shortlist_members.csv", index=False)
    # Use every selected star in the background; no randomized plot subsampling.
    panels = [("ra", "dec", "RA (deg)", "Dec (deg)"),
              ("x_kpc", "y_kpc", "x (kpc)", "y (kpc)"),
              ("y_kpc", "z_kpc", "y (kpc)", "z (kpc)"),
              ("vx_kms", "vy_kms", "vx (km/s)", "vy (km/s)"),
              ("vy_kms", "vz_kms", "vy (km/s)", "vz (km/s)"),
              ("pmra", "pmdec", "pmRA (mas/yr)", "pmDec (mas/yr)")]
    for row in shortlist.itertuples():
        group = stars.loc[stars.cluster_id == row.cluster_id]
        fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout="constrained")
        for ax, (x, y, xlabel, ylabel) in zip(axes.flat, panels):
            ax.scatter(stars[x], stars[y], s=.3, color="0.7", alpha=.15, rasterized=True)
            points = ax.scatter(group[x], group[y], c=group.z_kpc, cmap="coolwarm", s=8)
            ax.set(xlabel=xlabel, ylabel=ylabel)
        fig.colorbar(points, ax=axes, label="Member z (kpc)", shrink=.7)
        fig.suptitle(f"Candidate {row.cluster_id}: {row.n_members} stars; {row.review_tier}\n"
                     f"seed min J={row.seed_jaccard_min:.3f}; direct 6D J={row.direct_6d_best_jaccard:.3f}; "
                     "unconfirmed")
        fig.savefig(output / f"candidate_{row.cluster_id:03d}.png", dpi=140)
        plt.close(fig)
    provenance = {"run": str(run),
        "inputs_sha256": {name: hashlib.sha256((run / name).read_bytes()).hexdigest()
                          for name in ["assigned_stars.csv", "candidate_catalog.csv", "seed_stability.csv", "summary.json"]},
        "selected_stars": len(stars), "candidates": len(catalog),
        "shortlisted_ids": shortlist.cluster_id.tolist(),
        "scientific_status": "Descriptive computational review; no known-stream recovery or discovery established."}
    (output / "review_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    lines = ["# Candidate evidence review", "", provenance["scientific_status"], "",
        "The input memberships are unchanged. Review tiers prioritize follow-up and are not calibrated probabilities.", "",
        "## Reproducible triage rules", "",
        "Priority: minimum seed Jaccard >= 0.7 over all configured extra seeds and direct-6D Jaccard >= 0.5.",
        "Secondary: direct-6D Jaccard >= 0.1, or complete seed evidence with minimum Jaccard >= 0.7, position elongation >= 2 and raw 3D velocity dispersion <= 60 km/s. All others are deferred, not rejected.",
        "These exploratory thresholds were chosen after inspecting this run and require sensitivity testing. Rank is tier, descending direct-6D Jaccard, descending minimum seed Jaccard, then ID. No detection significance is implied.", "",
        "Near-boundary flag means >= half the members lie within 0.5 kpc above the configured |z| cut. It identifies a selection concern, not an artifact diagnosis. Raw velocity dispersion includes gradients and measurement error; elongation alone does not identify a stream.", "",
        "## Shortlist", "", "| ID | Tier | N | Min seed J | Direct 6D J | Elongation | Raw velocity dispersion (km/s) | Near z cut |",
        "|---|---|---|---|---|---|---|---|"]
    for r in shortlist.itertuples():
        lines.append(f"| {r.cluster_id} | {r.review_tier} | {r.n_members} | {r.seed_jaccard_min:.3f} | {r.direct_6d_best_jaccard:.3f} | {r.position_elongation:.2f} | {r.velocity_dispersion_3d_kms:.1f} | {r.fraction_within_0p5_kpc_of_z_cut:.1%} |")
    lines += ["", "Each shortlisted ID has a six-panel evidence PNG with all selected stars in gray and members colored by z. RA is shown in its native 0–360 degree convention without wrap correction; projection appearance is descriptive.", "",
        "## Physical follow-up still required", "",
        "Inspect morphology and local control samples; assess bound-cluster alternatives, parameter dependence, distance inference and correlated measurement errors before orbital follow-up. Seed stability is not an uncertainty experiment. Density grouping alone does not establish astronomical identity.", "",
        "Input checksums are in review_provenance.json. The source summary lacks a query manifest establishing full-sky completeness; coverage cannot be inferred from the selected table alone."]
    (output / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.run, args.output)
