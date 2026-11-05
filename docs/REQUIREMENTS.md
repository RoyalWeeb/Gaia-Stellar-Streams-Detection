# Mapping to the supplied presentation

| Proposal item | Implementation / status |
| --- | --- |
| Gaia DR3 ADQL via astroquery | `archive.py`; exact query and job IDs logged in the download manifest; live service run remains unverified here |
| RUWE < 1.4, parallax S/N > 5, RV error < 5 km/s | Query predicates plus locally checked strict thresholds |
| Galactocentric x,y,z,vx,vy,vz | Unit-aware Astropy transforms, explicit solar frame; round-trip test |
| Halo working sample, abs(z) > 3 kpc | Local chunked physical-coordinate filter |
| UMAP 2-3 dimensions | Configurable 2 or 3 components; default 3 |
| HDBSCAN; no fixed cluster count; noise | Actual scikit-learn-contrib HDBSCAN implementation, -1 noise labels |
| Cluster persistence and stability | HDBSCAN persistence, multiple-seed Jaccard checks, direct 6D control |
| Catalog cross-match | Removed from the active project at the user's request; old artifacts remain historical |
| Matplotlib and Plotly | Static overview and offline interactive HTML explorer |
| Local candidate dashboard | Linked 3D/2D saved-result views, exact-ID search, filters, coloring, bounded display sampling and Reset |
| Algorithm comparison dashboard / evidence downloads | Removed from the active project at the user's request |
| Jupyter Notebook and Conda | Notebook, environment.yml, CLI and packaging files |
| Gala / orbital follow-up | A future scientific extension; not required for Astropy coordinate transforms; optional dependency declared |
| Dask/Vaex for billions of rows | Portable chunked pandas ingestion provided; in-memory learner capped; distributed clustering is not implemented |
| About 2.1 million halo stars | Not assumed or claimed; actual selection counts exported |
| 20+ streams, including GD-1 and Sagittarius | Research target; requires real data and external validation; not a demonstrated result |
| Full-sky, GPU, learned embeddings, chemical fusion, DR4/DR5 | Future extensions described in the report |

The core candidate-search architecture remains active. A saved real Gaia DR3 run
and synthetic demonstrations are bundled; no verified published membership
catalog has established known-stream recovery. The original proposal, PDFs and
older output folders can describe earlier features, so consult the current README
for supported commands. Neither synthetic results nor density-group counts
establish a confirmed astronomical stream.
