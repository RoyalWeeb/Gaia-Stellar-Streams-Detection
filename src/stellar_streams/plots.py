from pathlib import Path
import html
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go

COLORS = ["#14b8a6", "#f59e0b", "#a78bfa", "#f472b6", "#38bdf8", "#84cc16", "#ef4444"]


def make_plots(assigned, catalog, summary, output, config):
    output = Path(output)
    sample = assigned.sample(n=min(len(assigned), config.plot_max_stars), random_state=config.seed)
    kind = "SYNTHETIC DEMONSTRATION" if summary["data_kind"] == "synthetic_toy" else "CANDIDATE SEARCH"
    panels = [("umap_1", "umap_2", "UMAP 1 (dimensionless)", "UMAP 2 (dimensionless)"),
              ("x_kpc", "y_kpc", "Galactocentric x (kpc)", "Galactocentric y (kpc)"),
              ("ra", "dec", "ICRS RA (deg)", "ICRS Dec (deg)"),
              ("vx_kms", "vy_kms", "vx (km/s)", "vy (km/s)")]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for ax, (x, y, xlabel, ylabel) in zip(axes.flat, panels):
        noise = sample.loc[sample.cluster_id < 0]
        ax.scatter(noise[x], noise[y], s=3, c="#94a3b8", alpha=.25, rasterized=True, label="Noise")
        for label in sorted(sample.cluster_id.unique()):
            if label < 0:
                continue
            group = sample.loc[sample.cluster_id == label]
            ax.scatter(group[x], group[y], s=6, color=COLORS[int(label) % len(COLORS)],
                       alpha=.8, rasterized=True, label=f"Candidate {label}")
        ax.set(xlabel=xlabel, ylabel=ylabel)
        ax.grid(alpha=.12)
    if summary["n_clusters"] < 10:
        axes.flat[0].legend(fontsize=8, markerscale=2)
    fig.suptitle(f"{kind} | UMAP + HDBSCAN | {len(assigned):,} selected stars", fontsize=14)
    fig.savefig(output / "phase_space_overview.png", dpi=170)
    plt.close(fig)
    html_figs = []
    for index, (x, y, xlabel, ylabel) in enumerate(panels):
        chart = go.Figure()
        for label in sorted(sample.cluster_id.unique()):
            group = sample.loc[sample.cluster_id == label]
            chart.add_trace(go.Scattergl(
                x=group[x], y=group[y], mode="markers",
                name="Noise" if label < 0 else f"Candidate {label}",
                marker={"size": 4 if label < 0 else 6,
                        "color": "#64748b" if label < 0 else COLORS[int(label) % len(COLORS)],
                        "opacity": .3 if label < 0 else .85},
                customdata=group[["source_id", "membership_strength"]].to_numpy(dtype=object),
                hovertemplate="ID: %{customdata[0]}<br>x: %{x:.3f}<br>y: %{y:.3f}<br>Density strength: %{customdata[1]:.3f}<extra>%{fullData.name}</extra>"))
        chart.update_layout(template="plotly_dark", height=470, paper_bgcolor="#111827", plot_bgcolor="#111827",
                            margin={"l": 65, "r": 20, "t": 25, "b": 55}, xaxis_title=xlabel, yaxis_title=ylabel)
        html_figs.append(chart.to_html(full_html=False, include_plotlyjs=True if index == 0 else False))
    table = catalog.head(200).round(3).to_html(index=False, classes="catalog", escape=True)
    content = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gaia stellar stream candidates</title>
<style>body{{margin:0;background:#080f1e;color:#e2e8f0;font:16px system-ui,sans-serif}}main{{max-width:1240px;margin:auto;padding:40px 24px}}
h1{{font-size:38px;margin:10px 0}}h2{{font-size:22px}}.eyebrow{{color:#2dd4bf;letter-spacing:2px;font-size:12px}}
p{{line-height:1.6;max-width:1000px;color:#cbd5e1}}.metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:26px 0}}
.metric{{background:#111827;border:1px solid #263348;border-radius:12px;padding:20px;flex:1;min-width:150px}}
.value{{display:block;font-size:30px;color:#2dd4bf}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.panel{{background:#111827;border-radius:12px;overflow:hidden}}.panel h2{{margin:20px 22px 0}}a{{color:#5eead4}}
.scroll{{overflow:auto}}table{{border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #334155;white-space:nowrap}}
th{{text-align:left;color:#5eead4}}.note{{padding:16px;border-left:3px solid #2dd4bf;background:#111827}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}h1{{font-size:29px}}}}
</style></head><body><main><div class="eyebrow">GAIA DR3 / UNSUPERVISED MACHINE LEARNING</div>
<h1>Stellar stream candidate explorer</h1><p class="note"><strong>{kind}.</strong> Density candidates require astronomical follow-up.
HDBSCAN strengths are not calibrated membership probabilities. Synthetic trails are not GD-1, Sagittarius, or newly discovered streams.</p>
<div class="metrics"><div class="metric">Selected stars<span class="value">{len(assigned):,}</span></div>
<div class="metric">Density candidates<span class="value">{summary['n_clusters']}</span></div>
<div class="metric">Noise fraction<span class="value">{summary['noise_fraction']:.1%}</span></div>
<div class="metric">Original 6D candidates<span class="value">{summary['direct_6d_clusters']}</span></div></div>
<p>Hover for source identifiers. Zoom, pan, or select legend entries to inspect groups. Displaying {len(sample):,} stars;
all {len(assigned):,} selected stars are saved in assigned_stars.csv. Embedding axes have no physical units.</p>
<div class="grid">{''.join('<section class="panel"><h2>'+html.escape(title)+'</h2>'+chart+'</section>' for title,chart in zip(['UMAP embedding','Galactic positions','Sky coordinates','Galactic velocities'],html_figs))}</div>
<h2>Candidate catalog</h2><p>Best Jaccard scores compare memberships across seeds and against direct 6D clustering. A high score supports reproducibility, not physical confirmation.</p>
<div class="scroll">{table}</div><p>Showing at most 200 catalog entries. <a href="candidate_catalog.csv">Download full catalog</a> ·
<a href="summary.json">Run summary</a> · <a href="assigned_stars.csv">All selected stars</a></p></main></body></html>"""
    (output / "explorer.html").write_text(content, encoding="utf-8")
