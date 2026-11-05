# Verification history

## Candidate reviews and guided local-data loading — 2026-10-29

- Full current suite: **44 passed** on Windows / Python 3.14.8 with Dash 4.4.1.
  Fourteen upstream Dash DataTable deprecation warnings remain. The test
  temporary directory was placed inside the project workspace.
- Review checks cover persistence across app instances, exact run binding,
  stale-edit rejection, invalid/corrupt review-file preservation, selection
  guards, review-status filtering and isolation between saved runs. The
  analytical candidate catalog is not edited by review saves.
- Import checks cover full-file quality/halo counts, explicit cap/sampling
  decisions, empty selections, missing columns, invalid exact IDs, upload
  encoding/extensions/path traversal, bounded configuration, changed-settings
  guards and input-snapshot hash verification before fitting. Callback tests
  also verify that a stale preview disables and rejects processing.
- Browser acceptance previewed `data/gaia_halo.csv`: **99,951 input / quality /
  halo / selected** rows with the current cuts. The original result files were
  preserved and no review was saved to that original Gaia run.
- A browser file-picker upload of a **500-row subset of the real Gaia input**
  completed the entire preview → background pipeline → open-results workflow.
  The acceptance run used 15 UMAP neighbours, minimum cluster size 20 and minimum
  samples 5, with two extra seeds. It produced **10 density candidates** in a
  recorded 14.2 seconds. This small ordered subset is a UI acceptance sample,
  not a survey benchmark or a scientific discovery claim.
- A test-only review in that new run was saved as Needs investigation with an
  explicit interface-verification note. The saved run, status and note reopened
  after browser reload and server restart. Review filtering, per-run display
  counts and the dark editor contrast were checked in the browser. The original
  99,951-star run remains available, and Show all stars restores its full cap.
- Screenshots and the acceptance input are under
  `outputs/dashboard_acceptance_20261029/`; imported results, snapshots and
  worker logs are under `outputs/dashboard_workspace/`. The existing project
  report is unchanged and predates these two additions.

## Compact dropdowns and full Gaia display — 2026-10-29

- Full suite: **34 passed** after adding regression tests for full-cap display,
  exact source membership in all four views, and raising the cap without changing
  analytical data. No clustering was refitted.
- The local explorer on port 8051 now loads `outputs/gaia_halo_run` with
  `--display-cap 99951`. Browser status confirmed **99,951 selected / 99,951
  rendered**, with noise visible and candidate filters cleared. A read-only
  membership check includes all 74,438 noise sources and all candidate members.
- Dropdown options now use 30-pixel border-box rows (previously 54 pixels), with
  centered text and a 32-pixel search field. Browser measurements confirmed
  option alignment and that selected text and control centers coincide.
- Added loaded-run information and Show all stars, using the loaded row count
  rather than a fixed Gaia run size. Browser check lowered the cap to 500 and
  restored it to 99,951 with the new button. Visibility filters still apply.
- Screenshot: `outputs/explorer_full_gaia_dropdown_20261029.jpg`.

## Explorer simplification — 2026-10-29

The current revision removes the standalone algorithm-comparison workflow,
published-stream reference-validation workflow and dashboard evidence downloads.
It keeps the core candidate search, synthetic truth evaluation, seed/direct-6D
diagnostics, local saved-result explorer and offline HTML export.

The explorer revision adds readable dropdown search fields, explicit bounded
minus/plus controls, and Reset for initial controls, filters, table state and plot
cameras/zoom. Acceptance for this revision:

- Full suite: **32 passed** on Windows / Python 3.14.8, including CLI removal,
  all-noise/2D views, exact source IDs, linked highlighting, Reset state and
  numeric-boundary regression tests. Dash DataTable emits nine upstream
  deprecation warnings; the optional Dash dependency remains below version 5.
- A fresh small synthetic CLI run completed in
  `outputs/dashboard_simplified_demo_20261029`: 213 selected stars, seven density
  candidates, offline HTML/static plots, toy-truth evaluation and seed/direct-6D
  diagnostics. No reference outputs were generated. The offline HTML contains
  embedded scripts and four plots; notebook/report generator sources compile.
- Browser checks passed for searchable method/candidate/color dropdowns with
  visible text and focus; consecutive count clicks (250 → 252 → 251); a 0.05
  fractional step; blank optional maximum becoming one; and Reset restoring
  numeric defaults, candidate/color, source search, noise and table search.
  Position and embedding plots still rendered after Reset. Automated callbacks
  verify cleared table sort/page/cell state and changed Plotly revision tokens
  for camera/zoom reset. Screenshot: `outputs/explorer_search_20261029.jpg`.
- The running local explorer was refreshed on port 8051. Existing historical
  datasets and outputs were preserved. No full Gaia clustering rerun was needed.

Older test counts below are historical and do not certify this revision.

Run the current tests with:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Current usage is in `README.md` and `DASHBOARD.md`. Saved results, reference files,
and comparison experiment folders from earlier versions were preserved. No
scientific confirmation follows from removing or changing interface features.

## Historical dashboard acceptance — 2026-10-21

This section records the earlier implementation, including features since
removed. Its old command options and comparison/reference tests are not current
usage instructions.

- Python 3.14.8 on Windows, Dash 4.4.1, Plotly 6.9.0 and psutil 7.2.2 were used.
  The earlier suite passed 31 tests. Additional targeted dashboard checks passed.
  Dash DataTable emitted upstream deprecation warnings.
- A genuine small synthetic CLI run produced 213 selected stars and seven UMAP
  density candidates, plus plots, offline HTML and then-supported reference and
  comparison artifacts. These counts are toy outcomes, not expected real-data
  values. Historical folders are retained under `outputs/dashboard_demo`.
- Earlier browser checks covered candidate selection, linked views, full-member
  diagnostics, cap, noise toggle and size filtering, as well as the now-removed
  method-comparison/reference interactions. Exact source lookup displayed
  `900000000000000240` without rounding. Browser logs reported no errors.
- The read-only real-run check loaded 99,951 selected stars and 94 candidates.
  A 500-star display retained all 138 members of candidate 5. This did not refit
  the approximately 100,000-star sample.
- The sandbox denied localhost sockets initially; an approved localhost-only
  server was reachable and served local Dash/Plotly assets. No external scripts
  were needed to browse saved results.

The previous reference demonstration used clearly labeled synthetic truth. Real
published memberships had not established known-stream recovery or a discovery.

## Original delivery checks

The original delivery used Python 3.12.14 and dependencies recorded in
`requirements-tested-py312.txt`. Its 17 passing tests covered strict quality
thresholds, missing values, large identifiers, coordinate round trips, sampling,
pagination/resume, cache integrity, input sanitization, no-cluster behavior and
then-supported reference calculations. Those old counts are retained as history.

The complete synthetic pipeline exercised observations, quality cuts,
Galactocentric halo selection, robust scaling, UMAP, HDBSCAN, two extra seeds,
direct-6D control, truth evaluation, plots and offline HTML. Eight notebook code
cells executed in-process. A ten-page report was rendered and inspected. The
original offline explorer was checked for embedded JavaScript and local links;
browser rendering was verified in the later dashboard extension.

A TCP-based Jupyter kernel was blocked in that delivery environment. In-process
execution verified the Python cells; normal interactive Jupyter startup remained
a machine-specific check.

## Historical measured synthetic experiment

| Quantity | Result |
| --- | --- |
| Raw / quality-selected / halo-selected rows | 4,320 / 4,200 / 3,313 |
| HDBSCAN density candidates | 7 |
| Noise rows / fraction | 993 / 29.97% |
| Direct-6D-supported candidates (Jaccard >= 0.5) | 3 |
| Injected toy trails recovered | 3 of 3 |
| Best-cluster recall for each toy trail | 100% |
| Best-cluster precision for toy trails 1, 2, 3 | 94.12%, 88.24%, 94.12% |
| Field assignment fraction across all candidate groups | 61.70% |
| Adjusted Rand index including field label | 0.2036 |

The four broad background groups had direct-6D Jaccard below 0.03; the three toy
trail groups exceeded 0.83. Restricting descriptively to those groups left 62
field stars among 782 members. These are toy-specific observations, not
validated candidate-rejection rules or real Gaia performance estimates.

The initial EOM results remain under `outputs/baseline_eom/results`. The old
16-setting `toy_parameter_comparison.csv` changed HDBSCAN settings on a fixed
seed-42 embedding; it did not refit UMAP per row. Final leaf settings were chosen
after inspecting that toy example, so its recovery was not held-out evaluation.

## Scientific limits

No known named stream recovery, new discovery, correlated-error propagation,
parallax zero-point correction, orbital/chemical confirmation, billion-row/GPU
clustering, or distributed processing has been established. Python 3.11 runtime
execution has not been checked here. The current program has no published-member
validation interface; earlier matching artifacts do not supply confirmation.

The bundled PDF and notebook are historical explanatory artifacts. Scripts for
regenerating them remain in `scripts/`, but their text can refer to earlier
features. Use the current README for supported installation and commands.
