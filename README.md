# Discovering Stellar Streams in Gaia DR3

An educational candidate-search pipeline: query Gaia DR3, filter measurements,
transform to Galactocentric 6D phase space, scale features, embed with UMAP,
cluster with HDBSCAN, inspect reproducibility diagnostics, and explore candidates.

**Scientific status:** the code supports synthetic demonstrations and processing
local Gaia DR3 data. Generated run outputs and local catalogues are excluded from
the GitHub repository. The demonstrated Gaia DR3 run processed 99,951 selected
stars, producing 94 UMAP + HDBSCAN density candidates and four direct-6D control
groups. These are candidates; known-stream recovery and new-stream discovery
have not been established. GD-1, Sagittarius, 20+ recovered streams, and a
2.1-million-star halo sample remain proposal targets.

The current dashboard focuses on the candidate explorer. Algorithm comparison,
published-stream reference validation, and evidence-download controls were
removed on 2026-10-29. Older output folders and reports are retained as historical
artifacts; they do not describe additional active dashboard features.

## Installation

Use Python 3.11 or newer. The original delivery was verified on Python 3.12;
the dashboard extension was exercised on Python 3.14.8 on Windows. Python 3.11
runtime execution has not been verified in this workspace.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[dashboard,dev]"
```

Using the virtual environment's Python directly avoids PowerShell activation
policy issues. The dashboard is optional: base pipeline installation can use
`python -m pip install -e .`. Notebook dependencies are available with
`python -m pip install -e ".[notebook]"`. On macOS/Linux use `.venv/bin/python`
or activate with `source .venv/bin/activate`. The included `environment.yml`
also provides a Conda workflow.

## Explore the existing real Gaia results

From the project folder in Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/gaia_halo_run --port 8051
```

To load this real run and display all 99,951 selected stars immediately:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/gaia_halo_run --display-cap 99951 --port 8051
```

The synthetic demo contains a different, much smaller sample. The real run's
saved default displays 20,000 of its 99,951 stars; that is only a plotting cap.
Use **Show all stars** to raise the cap to the loaded run's full count. Keep
noise visible and clear candidate filters to include every selected star.
No clustering is repeated. Rendering four full-size views can take longer;
lower Maximum rendered stars again if the browser becomes slow.

Open `http://127.0.0.1:8051`. Dash serves its scripts, Plotly and styles locally;
no internet connection or refitting is needed to browse saved results. Stop the
server with Ctrl+C in the terminal. Existing offline `explorer.html` exports can
also be opened directly in a browser.

The explorer links 3D Galactic positions, 3D UMAP (or 2D UMAP for a two-component
run), ICRS sky and Galactic velocities. Search/sort the candidate table, click a
cell or choose a candidate, filter by size/stability/persistence, toggle noise,
and color by candidate, z, vx, RUWE or parallax S/N. Exact `source_id` lookup
searches all selected stars, including sources outside the display sample.
Physical axes have kpc or km/s units; embedding axes are dimensionless.

Dropdown search fields and results use readable contrast and focus highlights.
Numeric minus/plus controls update counts by one and fractional thresholds by
0.05, respecting their bounds. **Reset** restores initial controls, filters,
table search/sort/page/selection and plot cameras/zoom. The Method box identifies
the loaded UMAP + HDBSCAN run.

The display cap comes from the saved `plot_max_stars`, defaults to 20,000 when
absent, and can be overridden using `--display-cap`. Sampling affects rendered
points only. Counts distinguish total selected stars, rendered stars, and full
versus rendered candidate membership. Every diagnostic uses all assigned members.
See [explorer controls and display protocol](docs/DASHBOARD.md).

## Review candidates and load local data in the dashboard

**Candidate review** shows full-member diagnostics and median Galactic positions
and velocities for the selected group. Choose Unreviewed, Shortlisted,
Needs investigation or Rejected, add notes, and click **Save review** before
switching candidates. Decisions are saved in `candidate_reviews.json` alongside
that run's results and survive a browser/server restart. The review-status filter
and catalog column help build a shortlist. These are reviewer decisions, not
confirmed astronomical classifications. Reset clears display settings without
deleting saved reviews.

Under **Your saved runs → Load Gaia data**, choose a CSV/VOTable or enter its
local path, select the data origin, and adjust selection/clustering settings.
**Preview selection** checks required columns and scans the complete file to
show input, quality-selected, halo-selected and fit counts. **Start processing**
becomes available only for a valid preview with unchanged file/settings. A
background worker reports its current stage while the existing explorer stays
available. When finished, click **Open new results**; completed imports also
remain in the saved-run selector after restarting the dashboard.

Uploads are limited to 64 MiB; larger catalogues use the local-path option.
CSV reading is chunked, while VOTable parsing is eager. Input snapshots,
selection previews, processing logs and new result folders are stored under
`outputs/dashboard_workspace/<job-id>/` when starting from the bundled Gaia run.
Each import gets a fresh folder. The original catalogue and existing analytical
results are preserved. The selected-star limit is at most 100,000 in this UI;
excess eligible rows block processing unless uniform sampling is explicitly
selected. The same CLI pipeline performs the actual analysis.

## Synthetic demonstration

Generate a small, reproducible **synthetic** run in a fresh output folder:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli demo --output outputs/my_explorer_demo --config configs/dashboard_demo.yaml --field-stars 240 --members-per-stream 40
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/my_explorer_demo/results
```

For the larger default toy demonstration:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli demo --output outputs/my_demo --config configs/default.yaml
```

The default generator creates 3,600 field stars and three toy trails of 240
stars each. It converts synthetic Galactocentric vectors to Gaia-like ICRS
observables, adds independent measurement noise, and injects 120 bad-quality
records. Separate truth labels never enter the learning features. These toy
trails are not named observed streams. First execution can be slower while
UMAP's numerical routines compile.

## Download and process real Gaia DR3 observations

Archive queries require an internet connection. Public reads do not require
account credentials. Choose new file/output names for different selections:

```powershell
# Retrieve the complete random-index subset passing the archive quality cuts:
.venv\Scripts\python.exe -m stellar_streams.cli fetch --output data/gaia_dr3_new.csv --page-size 10000 --max-rows 0 --random-index-max 10000000 --config configs/default.yaml

# Apply local halo selection and generate density candidates:
.venv\Scripts\python.exe -m stellar_streams.cli run --input data/gaia_dr3_new.csv --output outputs/gaia_dr3_new_run --config configs/default.yaml --data-kind gaia_dr3

.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/gaia_dr3_new_run
```

`random_index` selects a reproducible approximate random subset of Gaia; its
threshold is not the number of rows requested. `--max-rows 0` retrieves the whole
selected subset. A positive row limit stops in `source_id` order, which encodes
sky location, so truncation is not a uniform full-sky sample. The query manifest
records this distinction. Repeat an identical download command to resume cached,
checksummed pages after interruption. Different settings require a new filename.

The halo cut is applied locally after the coordinate transform. Archive quality
predicates never replace the exact Galactocentric `abs(z_kpc) > 3` condition with
a sky-latitude approximation. Counts downloaded, quality-selected and halo-selected
will differ. Test a small download first; TAP service times and quotas vary.

## Your own Gaia file

CSV supports chunked processing. `.vot`, `.votable` and `.xml` VOTables are also
accepted, but initial VOTable parsing is eager. See
[the data dictionary](docs/DATA_DICTIONARY.md) for required columns and units.

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli run --input data/my_gaia.csv --output outputs/my_run --config configs/default.yaml --data-kind gaia_dr3
```

Each selected star needs one unique DR3 `source_id`. Do not concatenate
overlapping downloads. Preserve identifiers as exact integers or decimal strings;
float64 cannot represent Gaia identifiers exactly. Do not silently substitute
identifiers from another Gaia release.

## Saved outputs and candidate review

| File | Meaning |
| --- | --- |
| `assigned_stars.csv` | All selected stars, observables, physical features, UMAP axes, candidate label, density strength, outlier score and direct-6D control label |
| `candidate_catalog.csv` | Full member counts, persistence, seed/direct-6D agreement, morphology and velocity diagnostics |
| `seed_stability.csv` | Best membership Jaccard across additional UMAP seeds |
| `summary.json` | Selection counts, configuration, input SHA-256, explicit frame, versions, runtime and scientific status |
| `candidate_reviews.json` | Saved reviewer statuses and notes, created when a review is saved; bound to this run |
| `toy_evaluation.json` | Synthetic-only truth evaluation when a demo is generated |
| `phase_space_overview.png` | Static UMAP, physical position, sky and velocity panels |
| `explorer.html` | Offline plots and candidate table |

The pipeline writes these files locally; the dashboard has no evidence-download
section. Label -1 denotes noise. Numeric IDs can change between runs, so compare
memberships rather than label numbers. Empty candidate catalogs are valid.

A reviewed density-candidate catalog and qualitative plots are retained under
`outputs/gaia_halo_review`. Regenerate this descriptive triage without refitting:

```powershell
.venv\Scripts\python.exe scripts/review_candidates.py --run outputs/gaia_halo_run --output outputs/gaia_halo_review_new
```

Review tiers prioritize follow-up; they are not astronomical classifications.
Older reference/comparison files may remain in historical output folders, but
the corresponding feature workflows are no longer part of the current CLI.

## Configuration and scale limits

Edit a copy of `configs/default.yaml`. The baseline uses three UMAP components,
30 neighbors, `min_dist=0`, HDBSCAN minimum cluster size 120, minimum samples 20
and leaf selection. Median/IQR scaling makes kpc and km/s features comparable;
position and velocity weights are configurable. Extra seeds 43 and 44 and a
direct scaled-6D control provide diagnostics alongside the seed-42 fit.

CSV loading and transforms are chunked; UMAP and HDBSCAN are **in memory**.
The default cap is 100,000 eligible halo stars. Exceeding it raises an error.
`sampling: uniform` instead keeps a reproducible uniform subset and records
sampling in the summary. Sampling can remove rare members. Billion-row,
distributed and GPU clustering remain future work.

## Verification and scientific interpretation

```powershell
.venv\Scripts\python.exe -m pytest -q
```

See [verification history](docs/VERIFICATION.md) and the bundled notebook/report
for earlier measured demonstrations. Historical reports may discuss removed
features; the current commands are documented here.

Streams are generally tidally stripped, unbound debris. A phase-space overdensity
may instead be a bound cluster, moving group, contamination or selection effect.
Neither UMAP separation nor HDBSCAN persistence proves a shared orbit. Density
strengths are not calibrated astronomical membership probabilities. Seed
reproducibility does not measure sensitivity to astrometric uncertainties.

The baseline uses uncorrected inverse positive parallax with S/N > 5, without
correlated-error propagation or parallax zero-point correction. Distance
inference, error resampling, selection analysis, and orbital/chemical follow-up
remain scientific work. No confirmed-stream or discovery claim is supported.
Official references are in `docs/REFERENCES.md`; proposal status is mapped in
`docs/REQUIREMENTS.md`.
