"""Read-only dashboard models and display sampling; no algorithm fits."""
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .preprocessing import normalize_ids

COLORS = ["#38bdf8", "#fbbf24", "#a78bfa", "#fb7185", "#34d399", "#e879f9", "#fb923c"]


def records(table):
    """JSON-safe missing values and exact string source IDs, including Plotly customdata."""
    return json.loads(table.to_json(orient="records"))


@dataclass
class ResultData:
    name: str
    stars: pd.DataFrame
    catalog: pd.DataFrame
    summary: dict


def load_results(path, name="saved"):
    path = Path(path)
    try:
        stars = pd.read_csv(path / "assigned_stars.csv", dtype={"source_id": "string"})
        catalog = pd.read_csv(path / "candidate_catalog.csv")
        summary = json.loads((path / "summary.json").read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot load results from {path}: {exc}") from exc
    if not isinstance(summary, dict) or not isinstance(summary.get("config", {}), dict):
        raise ValueError("Malformed summary.json: expected an object with an optional config object")
    required = {"source_id", "cluster_id", "x_kpc", "y_kpc", "z_kpc", "vx_kms", "vy_kms", "vz_kms"}
    if missing := required - set(stars):
        raise ValueError(f"Malformed assigned_stars.csv: missing {sorted(missing)}")
    coordinates = ["x_kpc", "y_kpc", "z_kpc", "vx_kms", "vy_kms", "vz_kms"]
    for column in coordinates:
        stars[column] = pd.to_numeric(stars[column], errors="coerce")
    if not np.isfinite(stars[coordinates].to_numpy(float)).all():
        raise ValueError("Malformed assigned_stars.csv: physical coordinates must be finite numbers")
    if "cluster_id" not in catalog:
        raise ValueError("Malformed candidate_catalog.csv: missing cluster_id")
    stars["source_id"] = normalize_ids(stars.source_id)
    if stars.source_id.duplicated().any():
        raise ValueError("Duplicate source_id in saved results")
    labels = pd.to_numeric(stars.cluster_id, errors="coerce")
    if not np.isfinite(labels).all() or ((labels % 1) != 0).any() or (labels < -1).any():
        raise ValueError("Malformed cluster_id in saved results")
    stars["cluster_id"] = labels.astype(int)
    if catalog.cluster_id.duplicated().any():
        raise ValueError("Duplicate candidate catalog IDs")
    sizes = stars.loc[stars.cluster_id >= 0].groupby("cluster_id").size()
    if set(catalog.cluster_id) != set(sizes.index):
        raise ValueError("Candidate catalog IDs do not match saved assignments")
    catalog["n_members"] = catalog.cluster_id.map(sizes).astype(int)
    for key in ["cluster_persistence", "mean_membership_strength", "seed_jaccard_mean", "direct_6d_best_jaccard",
                "position_elongation", "velocity_dispersion_3d_kms"]:
        if key in catalog:
            catalog[key] = pd.to_numeric(catalog[key], errors="coerce")
    return ResultData(name, stars, catalog, summary)


def filter_candidates(data, min_size=0, max_size=None, seed=0, direct=0, persistence=0):
    result = data.catalog.copy()
    result = result.loc[result.n_members.ge(min_size or 0)]
    if max_size is not None:
        result = result.loc[result.n_members.le(max_size)]
    for key, threshold in [("seed_jaccard_mean", seed), ("direct_6d_best_jaccard", direct), ("cluster_persistence", persistence)]:
        if threshold and threshold > 0:
            if key not in result:
                return result.iloc[:0]
            result = result.loc[pd.to_numeric(result[key], errors="coerce").ge(threshold)]
    return result


def display_sample(data, candidates, candidate=None, source=None, show_noise=True, cap=20000, seed=42):
    """A strict display cap. Source lookup always wins; analytic tables stay untouched."""
    cap = max(1, int(cap))
    stars = data.stars
    visible = stars.cluster_id.isin(candidates) | ((stars.cluster_id < 0) & show_noise)
    candidate_ids = set(stars.loc[stars.cluster_id.eq(int(candidate)), "source_id"]) if candidate is not None else set()
    focus = visible & stars.source_id.isin(candidate_ids)
    exact = stars.loc[stars.source_id.eq(source)].copy() if source else stars.iloc[:0].copy()
    budget = cap - len(exact)
    focus_rows = stars.loc[focus & ~stars.source_id.isin(exact.source_id)]
    background = stars.loc[visible & ~focus & ~stars.source_id.isin(exact.source_id)]
    focus_budget = min(budget, max(1, cap // 2)) if len(background) else budget
    selected = focus_rows.sample(n=min(len(focus_rows), focus_budget), random_state=seed)
    rest = background.sample(n=min(len(background), budget - len(selected)), random_state=seed)
    # Fill spare slots with focus stars when background is smaller than its budget.
    spare = cap - len(exact) - len(selected) - len(rest)
    if spare > 0:
        extra = focus_rows.loc[~focus_rows.source_id.isin(selected.source_id)]
        selected = pd.concat([selected, extra.sample(n=min(len(extra), spare), random_state=seed)])
    rendered = pd.concat([rest, selected, exact]).copy()
    rendered["_candidate"] = rendered.source_id.isin(candidate_ids)
    rendered["_source"] = rendered.source_id.eq(source) if source else False
    counts = {"total": len(stars), "rendered": len(rendered), "visible": int(visible.sum()),
              "candidate_total": len(candidate_ids), "candidate_rendered": int(rendered._candidate.sum())}
    return rendered, counts


def empty_figure(message):
    fig = go.Figure()
    fig.add_annotation(text=message, x=.5, y=.5, xref="paper", yref="paper", showarrow=False)
    fig.update_layout(template="plotly_dark", height=390, paper_bgcolor="#101c30", plot_bgcolor="#101c30")
    return fig


def make_view(data, display, view="position", color="candidate", focused=False, revision=0):
    axes = {"position": (["x_kpc", "y_kpc", "z_kpc"], ["x (kpc)", "y (kpc)", "z (kpc)"]),
            "sky": (["ra", "dec"], ["ICRS RA (deg)", "ICRS Dec (deg)"]),
            "velocity": (["vx_kms", "vy_kms", "vz_kms"], ["vx (km/s)", "vy (km/s)", "vz (km/s)"])}
    if view == "embedding":
        prefix = "umap"
        keys = [f"{prefix}_{i}" for i in (1, 2, 3) if f"{prefix}_{i}" in data.stars]
        if len(keys) < 2:
            return empty_figure("No saved embedding for this method; inspect physical coordinates.")
        labels = [f"{prefix.upper()} {i+1} (dimensionless)" for i in range(len(keys))]
    else:
        keys, labels = axes[view]
    if not set(keys).issubset(display):
        return empty_figure("Coordinates unavailable in this saved run.")
    fig = go.Figure()
    three = len(keys) == 3
    def trace(group, title, tint=None, opacity=.8, size=3):
        if group.empty:
            return
        marker = {"size": size, "opacity": opacity}
        if tint:
            marker["color"] = tint
        elif color == "candidate":
            marker["color"] = ["#75859b" if c < 0 else COLORS[int(c) % len(COLORS)] for c in group.cluster_id]
        elif color in group:
            marker.update(color=group[color].tolist(), colorscale="Viridis", showscale=True,
                          colorbar={"title": {"text": {"z_kpc": "z (kpc)", "vx_kms": "vx (km/s)"}.get(color, color)}})
        else:
            marker["color"] = "#38bdf8"
        # Explicit lists avoid numeric encoding of identifiers or NumPy integer coercion.
        custom = [[str(r.source_id), int(r.cluster_id)] for r in group.itertuples()]
        kwargs = dict(x=group[keys[0]].tolist(), y=group[keys[1]].tolist(), mode="markers", name=title,
                      marker=marker, customdata=custom,
                      hovertemplate="Gaia ID: %{customdata[0]}<br>Candidate: %{customdata[1]}<br>%{x:.3f}, %{y:.3f}" +
                          (", %{z:.3f}" if three else "") + "<extra>%{fullData.name}</extra>")
        if three:
            fig.add_trace(go.Scatter3d(z=group[keys[2]].tolist(), **kwargs))
        else:
            fig.add_trace(go.Scattergl(**kwargs))
    focus = display._candidate | display._source
    trace(display.loc[~focus], "Background" if focused else "Selected stars", "#75859b" if focused else None,
          .12 if focused else .65)
    trace(display.loc[display._candidate & ~display._source], "Selected candidate", size=5)
    trace(display.loc[display._source], "Searched source", "#fb7185", size=9)
    fig.update_layout(template="plotly_dark", paper_bgcolor="#101c30", plot_bgcolor="#101c30", height=410,
                      margin={"l": 25, "r": 25, "b": 35, "t": 25}, uirevision=f"{data.name}-{view}-{revision}",
                      legend={"orientation": "h", "y": 1.05}, font={"size": 11})
    if three:
        fig.update_layout(scene={"xaxis_title": labels[0], "yaxis_title": labels[1], "zaxis_title": labels[2], "aspectmode": "data"})
    else:
        fig.update_layout(xaxis_title=labels[0], yaxis_title=labels[1])
    return fig
