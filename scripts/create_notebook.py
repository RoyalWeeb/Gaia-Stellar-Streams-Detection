"""Generate the teaching notebook. Run from the extracted project root."""
from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
m = nbf.v4.new_markdown_cell
c = nbf.v4.new_code_cell
nb.cells = [
 m('''# Discovering Stellar Streams in Gaia DR3
## Unsupervised learning in Galactic phase space

This notebook accompanies the supplied project proposal. It inspects the **executed synthetic demonstration** and explains the real Gaia pipeline. It does not claim real stream discoveries. The bundled trails are toy correlated trajectories rather than N-body simulations or named Galactic streams.

Run all cells after installing the project. A later opt-in cell can repeat the complete pipeline in a new folder.'''),
 c('''from pathlib import Path
import sys, json
import pandas as pd
import numpy as np
from IPython.display import display, Image, HTML

ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p / 'src/stellar_streams').exists()), None)
if ROOT is None:
    raise RuntimeError('Start Jupyter in the extracted Gaia_Stellar_Streams_Project folder')
sys.path.insert(0, str(ROOT / 'src'))
from stellar_streams.config import load_config
from stellar_streams.preprocessing import quality_filter, to_phase_space, FEATURES
from stellar_streams.pipeline import run_pipeline
from stellar_streams.synthetic import make_demo
config = load_config(ROOT / 'configs/default.yaml')
DATA = ROOT / 'outputs/demo/data'
RESULTS = ROOT / 'outputs/demo/results'
summary = json.loads((RESULTS / 'summary.json').read_text())
print('Data kind:', summary['data_kind'])
print('Executed Python:', summary['python'])
print('Configuration:'); display(pd.Series(config.to_dict()).to_frame('value'))'''),
 m('''## 1. Gaia-like input and quality cuts
Real input comes from `gaiadr3.gaia_source` through `astroquery`. The synthetic generator reverses Astropy's transform and adds small independent errors. Toy truth is stored in a separate file.

The strict cuts are RUWE < 1.4, positive parallax, parallax S/N > 5, and radial-velocity error < 5 km/s. Numeric inputs must also be finite. The project retains source IDs as decimal strings to avoid precision loss.'''),
 c('''raw = pd.read_csv(DATA / 'demo_gaia.csv', dtype={'source_id': 'string'})
clean = quality_filter(raw, config)
print(f'Raw: {len(raw):,}; quality survivors: {len(clean):,}')
display(raw.head())'''),
 m('''## 2. Transform to six physical features
For positive parallax in milliarcseconds, the baseline approximation is $d_{kpc}=1/\\varpi_{mas}$. `SkyCoord` uses RA, Dec, distance, `pm_ra_cosdec`, `pm_dec`, and radial velocity. The explicit Galactocentric frame is saved in each run summary.

This baseline does not correct the parallax zero point or propagate correlated astrometric uncertainties. Those changes are needed before making robust astrophysical claims.'''),
 c('''phase = to_phase_space(clean)
halo = phase.loc[phase.z_kpc.abs() > config.halo_z_min_kpc]
assert len(halo) == summary['selection']['halo_rows']
print('Halo selection:', len(halo), 'stars')
display(halo[FEATURES].describe().round(3))
display(pd.Series(summary['galactocentric_frame']).to_frame('frame value'))'''),
 m('''## 3. Robust scaling, UMAP and HDBSCAN
Only the six physical features enter the learner. Each is centered on the median and divided by its interquartile range. Positions and velocities can then be weighted separately.

The delivered demonstration uses 3 UMAP components, 30 neighbors, min_dist = 0, and HDBSCAN leaf selection with minimum cluster size 120 and minimum samples 20. Leaf selection was chosen after a small synthetic parameter comparison. These settings are not calibrated for real Gaia streams.

A first EOM baseline merged two toy trails with the background. The complete comparison is retained in `docs/toy_parameter_comparison.csv`. This illustrates why clustering hyperparameters and original-space diagnostics matter.'''),
 c('''assigned = pd.read_csv(RESULTS / 'assigned_stars.csv', dtype={'source_id': 'string'})
catalog = pd.read_csv(RESULTS / 'candidate_catalog.csv')
print('Density candidates:', summary['n_clusters'])
print('Noise fraction:', f"{summary['noise_fraction']:.1%}")
print('Candidates supported by direct 6D overlap:', summary['original_6d_supported_candidates'])
display(catalog.round(3))
display(Image(filename=str(RESULTS / 'phase_space_overview.png')))'''),
 m('''## 4. Evaluate toy recovery without leaking labels
The adjusted Rand index includes field stars as a single truth class. Per-trail precision and recall use the best overlapping predicted cluster; they can reveal merges and splits. The field false-assignment fraction is essential: assigning every trail star is not sufficient when most field stars are also assigned.'''),
 c('''evaluation = json.loads((RESULTS / 'toy_evaluation.json').read_text())
metrics = {k: v for k, v in evaluation.items() if k not in ['trail_recovery']}
display(pd.Series(metrics).to_frame('measured value'))
display(pd.DataFrame(evaluation['trail_recovery']).round(4))'''),
 m('''## 5. Stability and the original-6D control
UMAP seeds 43 and 44 are compared against seed 42 using best membership Jaccard overlap. Direct HDBSCAN on the same scaled 6D features provides an embedding-free control.

A direct-6D Jaccard of at least 0.5 is only a descriptive support flag. Groups remain unvalidated candidates. The seed checks do not perturb measurement errors, and numeric cluster IDs have no stable meaning across runs.'''),
 c('''stability = pd.read_csv(RESULTS / 'seed_stability.csv')
display(stability.round(3))
display(catalog[['cluster_id', 'n_members', 'seed_jaccard_mean',
                 'direct_6d_best_jaccard', 'original_6d_supported',
                 'velocity_dispersion_3d_kms']].round(3))'''),
 m('''## 6. Inspect the saved explorer
The offline HTML and local dashboard inspect saved assignments without fitting the learner again. The dashboard links physical positions, embedding, sky and velocity views. Candidate diagnostics use every member even when the displayed background is sampled.

The current dashboard focuses on candidate exploration; standalone algorithm comparison, published-reference validation and evidence-download panels have been removed.'''),
 c('''print('Offline explorer:', RESULTS / 'explorer.html')
print('Launch the dashboard from the project folder:')
print('python -m stellar_streams.cli dashboard --results outputs/demo/results')'''),
 m('''## 7. Repeat the full offline experiment
Set the flag below to True to generate a fresh synthetic dataset and execute every pipeline stage. A unique output folder preserves the bundled results. The first UMAP run may take longer because of compilation.'''),
 c('''RUN_NEW_EXPERIMENT = False
if RUN_NEW_EXPERIMENT:
    from datetime import datetime
    experiment = ROOT / 'outputs' / ('notebook_run_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    make_demo(experiment / 'data', seed=config.seed)
    run_pipeline(experiment / 'data/demo_gaia.csv', experiment / 'results', config,
                 truth=experiment / 'data/demo_truth.csv', data_kind='synthetic_toy')
else:
    print('Bundled results loaded. Enable RUN_NEW_EXPERIMENT to repeat the pipeline.')'''),
 m('''## 8. Query and analyze real Gaia DR3
Use these commands in a terminal from the project folder (internet required):

```bash
python -m stellar_streams.cli fetch --output data/gaia_dr3.csv --max-rows 0 --random-index-max 50000000 --config configs/default.yaml
python -m stellar_streams.cli run --input data/gaia_dr3.csv --output outputs/gaia_run --data-kind gaia_dr3 --config configs/default.yaml
```

The archive downloader uses source-ID pagination and caches each completed page. A positive `max-rows` truncates a sky-ordered sample; use a complete random-index subset for full-sky sampling. The local halo cut is applied after the physical transformation.

CSV preprocessing is chunked, but UMAP and HDBSCAN use RAM. The default maximum is 100,000 eligible stars. Exceeding it raises an error; explicit uniform sampling is configurable and reported.

Live ESA archive execution remains unverified in the delivery environment. The query/resume logic was tested against mocked responses.'''),
 m('''## Interpretation and next steps

- Inspect groups in physical positions, velocities and the sky, rather than only the embedding.
- Test independent synthetic seeds, field-only controls, parameter changes and uncertainty resampling before relying on recovery rates.
- Improve distances and model Gaia selection effects for distant halo stars.
- Follow up promising candidates with orbital and chemical evidence.
- Scale using physically motivated partitions with overlap and explicit reconciliation; separate shard labels cannot simply be concatenated.

Open `outputs/demo/results/explorer.html` directly for the interactive offline view. The PDF report and the README describe results, limits and future work.''')
]
nb.metadata = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
               'language_info': {'name': 'python', 'version': '3.12'}}
path = Path('notebooks/Gaia_Stellar_Streams.ipynb')
nbf.write(nb, path)
print(path)
