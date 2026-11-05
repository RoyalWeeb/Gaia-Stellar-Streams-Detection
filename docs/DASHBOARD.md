# Local candidate explorer

The dashboard explores saved candidate-search results, saves reviewer decisions,
and can process a new local catalogue in the background. It provides linked physical,
embedding, sky and velocity plots, a searchable candidate catalog, and candidate
diagnostics. Algorithm-comparison experiments, published-stream reference
validation, and the evidence-download section were removed on 2026-10-29.
Their old output folders remain historical artifacts and are not loaded by the
current explorer.

## Start the explorer

Install the optional dashboard extra and open the existing real Gaia run:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dashboard,dev]"
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/gaia_halo_run --port 8051
```

To start with all 99,951 stars in this saved real-data run:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/gaia_halo_run --display-cap 99951 --port 8051
```

This is separate from loading a synthetic demonstration, whose saved sample is
much smaller. The real run records 99,951 selected stars but a default plotting
cap of 20,000. **Show all stars** raises the display cap to the number of stars
in whichever run is loaded; it does not hardcode a Gaia sample size or refit
models. Noise must be shown and candidate filters cleared to render the entire
selected sample. The total and rendered counts make the distinction visible.
Full-size 3D views can take longer to load; reduce the cap if needed.

Open `http://127.0.0.1:8051`. The server binds to localhost by default and serves
Dash, Plotly and styles locally. An internet connection is unnecessary for
browsing saved results. Stop the server with Ctrl+C in its terminal. The original
offline `explorer.html` export is also retained.

For a fresh, small **synthetic** demonstration, choose an unused output folder:

```powershell
.venv\Scripts\python.exe -m stellar_streams.cli demo --output outputs/my_explorer_demo --config configs/dashboard_demo.yaml --field-stars 240 --members-per-stream 40
.venv\Scripts\python.exe -m stellar_streams.cli dashboard --results outputs/my_explorer_demo/results
```

## Views and selection

- Galactocentric positions: rotatable x/y/z in kpc.
- Saved embedding: rotatable 3D UMAP or a 2D view for two-component runs, with
  dimensionless axes.
- ICRS sky: RA and declination in degrees.
- Galactocentric velocities: rotatable vx/vy/vz in km/s.

The Method box identifies the saved UMAP + HDBSCAN run. It does not start fits
or load an algorithm-comparison experiment. Select a candidate through its
searchable selector or by clicking a catalog cell. Its members are highlighted
across the views while the background dims. Source identity is synchronized
using exact Gaia `source_id` strings, never sampled plot indices.

The dropdown search has a distinct input area with readable text, placeholder,
focus indicator and option highlighting. Search the Candidate box by ID. Color
choices include candidate label, Galactic z, vx and available quality fields.
Repeated palette colors do not establish candidate identity; selecting one group
mutes the others. Missing optional fields are explained instead of invented.

## Filters, numeric controls and Reset

Filter by minimum/maximum candidate size, mean seed Jaccard, direct-6D Jaccard,
and persistence. Positive diagnostic thresholds exclude candidates lacking that
diagnostic. Toggle noise independently. Gaia source search checks the complete
selected sample and includes a found source even if it was outside the initial
display sample or visibility filters.

The minus/plus controls update the input and plots immediately. Member and
rendered-star counts step by one; fractional diagnostic thresholds step by 0.05.
Controls respect each field's bounds, with fractions limited to [0, 1]. The
optional maximum-member filter starts blank; plus starts it at one and minus
is disabled while it is blank.

**Reset** returns the explorer to its initial settings: the saved method, no
candidate or searched source, candidate-label coloring, noise shown, the startup
display cap, zero minimum thresholds and no maximum-member filter. It also
clears catalog search/sort/page/cell selection and restores plot cameras/zoom.
The startup display cap is the saved `config.plot_max_stars` value (or 20,000
when absent), unless `--display-cap` overrides it.

## Candidate review workspace

Selecting a candidate opens full-member counts, persistence, density strength,
seed and direct-6D agreement, elongation, velocity spread and median physical
coordinates above the plots. The editor saves a decision and up to 10,000
characters of notes. Available decisions are Unreviewed, Shortlisted,
Needs investigation and Rejected. Use **Save review** before changing candidates.
The catalog includes review status and the review-status selector filters it.

Reviews are written atomically to `candidate_reviews.json` in the selected run.
They are bound to the run summary and candidate catalog, so reusing numeric
labels from a different fit cannot silently reuse decisions. A stale edit from
another browser tab is rejected rather than overwriting newer notes. A malformed
review file is reported and retained for recovery. Reset never deletes reviews.

## Guided local data loading

1. Expand **Load Gaia data** under **Your saved runs**.
2. Choose a CSV or VOTable (`.csv`, `.vot`, `.votable`, `.xml`), or select the
   local-path option. Relative paths start in the server's working directory.
3. Choose Gaia DR3 or other supplied observations; adjust quality cuts, the halo
   cut and selected-star limit. Optional clustering settings use the same
   defaults as the command-line pipeline.
4. Click **Preview selection**. This scans the entire file, checks columns and
   exact source IDs, and reports quality/halo rejections and sampling. The first
   selected rows are available for inspection.
5. Click **Start processing** after a valid preview. Changing the source or
   settings requires a new preview. Too few stars or a cap violation blocks it.
6. Follow the stage messages, then **Open new results**. Completed imports are
   also available from **Loaded results**, including after server restart.

Workers run in separate local processes; only one data job runs at a time per
dashboard. Progress describes completed stages and the current operation, not
an estimated runtime. Errors keep the previous explorer and failed-job log
available. A new preview creates a fresh job and never overwrites earlier runs.

The managed workspace defaults to `dashboard_workspace` beside the startup
result folder. It holds a copied input, `job.json` preview/progress, `worker.log`
and a new `results/` folder per job. Uploads support up to 64 MiB; local paths
avoid that upload limit. VOTables still parse eagerly, clustering remains in
memory and the guided workflow caps selected stars at 100,000. Uniform sampling
must be explicitly selected if the eligible sample exceeds the limit.

## Display sampling and scientific interpretation

The cap limits rendered stars only. It never changes clustering, member counts
or diagnostics. The searched source has first priority. Candidate members are
reserved before sampling the background; a large candidate can also be sampled
to keep within the cap. Counts show total selected stars, stars rendered, and
rendered versus full candidate membership. All candidate statistics use every
assigned member. Lower the cap if several 3D WebGL views strain browser memory.

The existing pipeline's seed and direct-6D controls remain diagnostic evidence.
Seed agreement does not propagate measurement uncertainty. HDBSCAN density
strengths are not calibrated probabilities of astronomical membership. A density
group can be a bound cluster, moving group, contamination or a selection effect;
none of these plots establishes a confirmed stellar stream.

## Implementation and compatibility

`dashboard.py` owns local startup, layout, run selection and review callbacks;
`dashboard_data.py` validates saved files, filters candidates, samples display
points and builds Plotly figures. `reviews.py` persists run-bound decisions.
`dashboard_import.py`, `dashboard_jobs.py` and `dashboard_worker.py` provide the
guided loader, isolated jobs and stage reporting. Scientific fitting remains
in the shared pipeline.
New pipeline runs still write analytical CSVs, summary and offline plots to their
output folder. There are no dashboard evidence-download controls.

The optional extra uses Dash >=3,<5. Project Python support remains >=3.11.
Previous runtime verification used Python 3.14.8 and Dash 4.4.1 on Windows;
Python 3.11 execution has not been verified in this workspace. Dash DataTable is
deprecated upstream, so the dependency remains pinned below Dash 5.
