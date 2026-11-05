"""Local candidate explorer, persistent reviews and guided data imports."""
from pathlib import Path
import json
import math
import threading
import pandas as pd
from .dashboard_data import load_results, filter_candidates, display_sample, make_view, records
from .reviews import ReviewStore, REVIEW_STATUSES
from .dashboard_jobs import ImportManager
from .dashboard_import import import_panel, register_import_callbacks

# id, label, lower, upper, step, initial
NUMERIC_CONTROLS = (
    ("cap", "Maximum rendered stars", 1, None, 1, None),
    ("min-size", "Minimum members", 0, None, 1, 0),
    ("max-size", "Maximum members (optional)", 0, None, 1, None),
    ("min-seed", "Minimum mean seed Jaccard", 0, 1, .05, 0),
    ("min-direct", "Minimum direct-6D Jaccard", 0, 1, .05, 0),
    ("min-persistence", "Minimum persistence", 0, 1, .05, 0),
)
VIEWS = ("position", "embedding", "sky", "velocity")


def bounded_value(value, lower, upper, default=None, integer=False):
    if value is None:
        return default
    try:
        value = float(value)
    except (ValueError, TypeError):
        return default
    if not math.isfinite(value):
        return default
    value = max(lower, value)
    if upper is not None:
        value = min(upper, value)
    return int(value) if integer else value


def create_app(results, display_cap=None, workspace=None):
    try:
        from dash import Dash, html, dcc, dash_table, Input, Output, State, ctx, no_update
    except ImportError as exc:
        raise RuntimeError('Install the dashboard extra: python -m pip install -e ".[dashboard]"') from exc
    data = load_results(results)
    initial_path = Path(results).resolve()
    manager = ImportManager(workspace or initial_path.parent / "dashboard_workspace")
    result_data = {"saved": data}
    review_stores = {"saved": ReviewStore(initial_path, data.catalog.cluster_id)}
    run_lock = threading.RLock()

    def get_run(key):
        key = key or "saved"
        with run_lock:
            if key not in result_data:
                path = manager.result_path(key)
                selected = load_results(path, name=key)
                review_stores[key] = ReviewStore(path, selected.catalog.cluster_id)
                result_data[key] = selected
            return result_data[key]

    def get_reviews(key):
        get_run(key)
        return review_stores[key or "saved"]
    default_cap = display_cap if display_cap is not None else data.summary.get("config", {}).get("plot_max_stars", 20000)
    if type(default_cap) is not int or default_cap < 1:
        raise ValueError("Display cap must be a positive integer")
    defaults = {key: default_cap if key == "cap" else initial for key, _, _, _, _, initial in NUMERIC_CONTROLS}
    app = Dash(__name__, assets_folder=str(Path(__file__).with_name("assets")), serve_locally=True,
               title="Gaia · Candidate observatory", update_title="Updating views…")
    app.server.config["MAX_CONTENT_LENGTH"] = 90 * 1024 * 1024

    def label(text, control):
        return html.Div([html.Label(text, htmlFor=control.id), control], className="control")

    def number(key):
        _, title, lower, upper, step, _ = next(s for s in NUMERIC_CONTROLS if s[0] == key)
        value = defaults[key]
        return html.Div([
            html.Label(title, htmlFor=key),
            html.Div([
                html.Button("−", id=key + "-down", type="button", n_clicks=0,
                            disabled=value is None or value <= lower,
                            **{"aria-label": "Decrease " + title}),
                dcc.Input(id=key, type="number", min=lower, max=upper, step=step,
                          value=value, debounce=False, className="number-value"),
                html.Button("+", id=key + "-up", type="button", n_clicks=0,
                            disabled=upper is not None and value is not None and value >= upper,
                            **{"aria-label": "Increase " + title}),
            ], className="number-control"),
        ], className="control")

    app.layout = html.Main([
        html.Header([
            html.Div("GAIA / PHASE-SPACE OBSERVATORY", className="eyebrow"),
            html.H1("Stellar stream candidates"),
            html.P("Explore saved stars, inspect candidate structure, and follow members across views."),
            html.P(f"Loaded run: {Path(results).name} · {len(data.stars):,} selected stars · {len(data.catalog):,} candidates", id="run-info", className="run-info"),
            html.P("SYNTHETIC DEMONSTRATION" if data.summary.get("data_kind") == "synthetic_toy" else "CANDIDATE SEARCH", id="data-badge", className="badge"),
            html.P("Density candidates require physical follow-up. HDBSCAN strengths are relative density scores, not calibrated probabilities of astronomical membership.", className="note"),
        ]),
        dcc.Store(id="active-run", data="saved"),
        dcc.Store(id="run-settings", data={"cap": default_cap, "total": len(data.stars), "run": "saved"}),
        import_panel(html, dcc, label, initial_path.name),
        html.Section([
            html.H2("Explore saved members"),
            html.Div([
                label("Method", dcc.Dropdown(id="method", options=[{"label": "UMAP + HDBSCAN · saved run", "value": "saved"}],
                    value="saved", clearable=False, searchable=True, className="explorer-dropdown")),
                label("Candidate (search by ID)", dcc.Dropdown(id="candidate", options=[], placeholder="All candidates",
                    searchable=True, className="explorer-dropdown")),
                label("Color", dcc.Dropdown(id="color", options=[{"label": title, "value": key} for title, key in [
                    ("Candidate label", "candidate"), ("Galactic z (kpc)", "z_kpc"), ("vx (km/s)", "vx_kms"),
                    ("RUWE (when available)", "ruwe"), ("Parallax S/N (when available)", "parallax_over_error")]],
                    value="candidate", clearable=False, searchable=True, className="explorer-dropdown")),
                html.Div([number("cap"), html.Button("Show all stars", id="show-all", type="button", n_clicks=0,
                    title="Set the display cap to every star in this loaded run; visibility filters still apply", className="show-all")], className="display-control"),
                label("Gaia source_id (exact decimal)", dcc.Input(id="source", type="text", value="", placeholder="900000000000000001", debounce=True)),
                label("Noise", dcc.Checklist(id="noise", options=[{"label": "Show noise", "value": "show"}], value=["show"])),
                label("Review status", dcc.Dropdown(id="review-filter", options=[{"label": "All review statuses", "value": "all"}] + [
                    {"label": status, "value": status} for status in REVIEW_STATUSES], value="all", clearable=False)),
            ], className="controls"),
            html.Div([number(spec[0]) for spec in NUMERIC_CONTROLS if spec[0] != "cap"] + [
                html.Div([html.Button("Reset", id="reset", n_clicks=0, type="button", title="Restore all initial explorer settings"),
                          html.Small("Restore controls, searches, table and views")], className="reset-control")
            ], className="controls"),
            html.P("Positive stability thresholds exclude candidates without that diagnostic. Select a candidate to dim the background. Source search checks all selected stars. Fraction controls step by 0.05; member and display counts step by one."),
            html.Div(id="selection-status", role="status"),
            html.Div(id="source-status", role="status"),
            html.Div(id="counts", className="note", role="status"),
            html.Div([
                html.Div([html.H2("Candidate review"), html.Div(id="details"),
                    html.P("Statistics use every assigned member. Seed agreement measures reproducibility, not measurement uncertainty.")], className="candidate-summary"),
                html.Div([
                    label("Decision", dcc.Dropdown(id="review-status", options=list(REVIEW_STATUSES), value="Unreviewed", clearable=False, disabled=True)),
                    html.Label("Review notes", htmlFor="review-notes"),
                    dcc.Textarea(id="review-notes", value="", placeholder="Describe the evidence, concerns and next checks for this candidate…", disabled=True, maxLength=10000),
                    html.Div([html.Button("Save review", id="save-review", n_clicks=0, type="button", disabled=True),
                              html.Small("Save changes before switching candidates.")], className="action-row"),
                    html.Div(id="review-meta", className="review-meta"),
                    html.Div(id="review-feedback", role="status", **{"aria-live": "polite"}),
                    dcc.Store(id="review-target"), dcc.Store(id="review-revision", data=0),
                ], className="review-editor"),
            ], className="review-workspace"),
            dcc.Loading(html.Div([
                html.Div([html.H3(title), dcc.Graph(id=view, config={"displaylogo": False})], className="plot")
                for title, view in [("Galactocentric positions · kpc", "position"), ("Embedding · dimensionless", "embedding"),
                                    ("ICRS sky · degrees", "sky"), ("Galactocentric velocities · km/s", "velocity")]
            ], className="plots")),
            html.H3("Candidate catalog · click a cell to select"),
            dash_table.DataTable(id="candidates", data=[], columns=[], sort_action="native", filter_action="native",
                sort_by=[], filter_query="", page_current=0, page_size=10,
                style_table={"overflowX": "auto"}, style_header={"backgroundColor": "#20334e", "color": "#d8f3ff"},
                style_cell={"backgroundColor": "#101c30", "color": "#dce6f3", "fontFamily": "system-ui", "fontSize": 12,
                            "textAlign": "left", "padding": "10px", "maxWidth": "280px", "whiteSpace": "normal", "border": "1px solid #263950"}),
        ]),
    ])

    # Synchronous browser-local stepping uses the latest value on each click;
    # Dash's native steppers are hidden to avoid deferred blur/debounce behavior.
    for key, _, lower, upper, step, _ in NUMERIC_CONTROLS:
        app.clientside_callback(
            """function(down, up, reset, all, run, current) {
                const trigger = dash_clientside.callback_context.triggered[0];
                if (!trigger) return dash_clientside.no_update;
                const id = trigger.prop_id.split('.')[0];
                const lower = %s, upper = %s, step = %s;
                if (id === 'reset' || id === 'run-settings') return %s;
                if (id === 'show-all') return %s;
                let value = current === null || current === undefined ? lower : Number(current);
                if (!Number.isFinite(value)) value = lower;
                let next = value + (id === %s ? -step : step);
                next = Math.max(lower, next);
                if (upper !== null) next = Math.min(upper, next);
                return Math.round(next * 1e10) / 1e10;
            }""" % (json.dumps(lower), json.dumps(upper), json.dumps(step), "run.cap" if key == "cap" else json.dumps(defaults[key]),
                     "run.total" if key == "cap" else "dash_clientside.no_update", json.dumps(key + "-down")),
            Output(key, "value"), Input(key + "-down", "n_clicks"), Input(key + "-up", "n_clicks"), Input("reset", "n_clicks"),
            Input("show-all", "n_clicks"),
            Input("run-settings", "data"),
            State(key, "value"), prevent_initial_call=True,
        )

        def disable_buttons(value, lo=lower, hi=upper):
            return value is None or value <= lo, hi is not None and value is not None and value >= hi
        app.callback(Output(key + "-down", "disabled"), Output(key + "-up", "disabled"), Input(key, "value"))(disable_buttons)

    @app.callback(Output("method", "value"), Output("color", "value"), Output("source", "value"), Output("noise", "value"),
        Output("candidates", "filter_query"), Output("candidates", "sort_by"), Output("candidates", "page_current"),
        Output("method", "search_value"), Output("candidate", "search_value"), Output("color", "search_value"),
        *[Output(view, prop) for view in VIEWS for prop in ("relayoutData", "selectedData", "clickData")],
        Output("review-filter", "value"),
        Input("reset", "n_clicks"), Input("active-run", "data"), prevent_initial_call=True)
    def reset_settings(clicks, run_key):
        return ("saved", "candidate", "", ["show"], "", [], 0, "", "", "", *([None] * (len(VIEWS) * 3)), "all")

    def filtered_catalog(min_size, max_size, seed, direct, persistence, run_key=None, review_filter=None):
        selected = get_run(run_key)
        table = filter_candidates(selected, bounded_value(min_size, 0, None, 0, True), bounded_value(max_size, 0, None, None, True),
                                  bounded_value(seed, 0, 1, 0), bounded_value(direct, 0, 1, 0), bounded_value(persistence, 0, 1, 0))
        try:
            reviews = get_reviews(run_key).all()
            table["review_status"] = [reviews.get(str(int(key)), {}).get("status", "Unreviewed") for key in table.cluster_id]
        except ValueError:
            table["review_status"] = "Unavailable"
        if review_filter and review_filter != "all":
            table = table.loc[table.review_status.eq(review_filter)]
        return table

    @app.callback(Output("candidates", "data"), Output("candidates", "columns"), Output("candidate", "options"),
        Output("candidate", "value"), Output("candidates", "active_cell"), Output("selection-status", "children"),
        Input("method", "value"), Input("min-size", "value"), Input("max-size", "value"), Input("min-seed", "value"),
        Input("min-direct", "value"), Input("min-persistence", "value"), Input("candidate", "value"),
        Input("candidates", "active_cell"), Input("reset", "n_clicks"), Input("active-run", "data"),
        Input("review-filter", "value"), Input("review-revision", "data"))
    def choose(method, min_size, max_size, seed, direct, persistence, candidate, active, reset, run_key, review_filter, revision):
        active_out = no_update
        if ctx.triggered_id in ("reset", "method", "active-run"):
            candidate, active_out = None, None
        elif ctx.triggered_id == "candidates" and active:
            candidate = str(active["row_id"]) if active.get("row_id") is not None else None
        filtered = filtered_catalog(min_size, max_size, seed, direct, persistence, run_key, review_filter)
        options = [{"label": f"Candidate {int(row.cluster_id)} · {row.n_members:,} stars", "value": str(int(row.cluster_id))} for row in filtered.itertuples()]
        status = ""
        if candidate is not None and str(candidate) not in {option["value"] for option in options}:
            candidate, active_out = None, None
            status = "Selection cleared because it does not meet the candidate filters."
        values = records(filtered)
        for row in values:
            row["id"] = str(row["cluster_id"])
        return values, [{"name": col.replace("_", " "), "id": col} for col in filtered.columns], options, candidate, active_out, status

    @app.callback(*[Output(view, "figure") for view in VIEWS], Output("counts", "children"), Output("details", "children"),
        Output("source-status", "children"), Input("candidate", "value"), Input("color", "value"), Input("cap", "value"),
        Input("source", "value"), Input("noise", "value"), Input("min-size", "value"), Input("max-size", "value"),
        Input("min-seed", "value"), Input("min-direct", "value"), Input("min-persistence", "value"), Input("reset", "n_clicks"),
        Input("active-run", "data"), Input("review-filter", "value"), Input("review-revision", "data"))
    def render(candidate, color, cap, source, noise, min_size, max_size, seed, direct, persistence, reset, run_key, review_filter, revision):
        if ctx.triggered_id == "review-revision" and review_filter in (None, "all"):
            return (no_update,) * 7
        data = get_run(run_key)
        filtered = filtered_catalog(min_size, max_size, seed, direct, persistence, run_key, review_filter)
        source = str(source or "").strip()
        source_status = ""
        if source:
            try:
                source = normalize_source(source)
                found = data.stars.loc[data.stars.source_id.eq(source)]
                source_status = (f"Source {source}: candidate {int(found.iloc[0].cluster_id)}; included even outside the initial display sample."
                                 if len(found) else f"Source {source} is absent from this selected sample.")
            except ValueError:
                source_status, source = "Invalid source_id: enter an unsigned decimal string.", ""
        if color != "candidate" and color not in data.stars:
            source_status += f" {color} is unavailable; candidate coloring is shown."
            color = "candidate"
        display, counts = display_sample(data, filtered.cluster_id, candidate, source, "show" in (noise or []),
            cap=bounded_value(cap, 1, None, default_cap, True), seed=data.summary.get("config", {}).get("seed", 42))
        figures = [make_view(data, display, view, color, candidate is not None or bool(source), revision=f"{run_key or 'saved'}:{reset or 0}") for view in VIEWS]
        count_text = (f"{counts['total']:,} total selected stars · {counts['rendered']:,} rendered · {counts['visible']:,} meet visibility filters. "
                      f"Candidate: {counts['candidate_rendered']:,} rendered / {counts['candidate_total']:,} full members. Display sampling never changes analyses.")
        if counts["rendered"] < counts["visible"]:
            count_text += " Display sample shown: use Show all stars to remove the display cap."
        elif counts["rendered"] == counts["total"]:
            count_text += " All selected stars are displayed."
        details = "No candidates after filtering." if filtered.empty else "Select a candidate to inspect its full-member details."
        if candidate is not None:
            row = data.catalog.loc[data.catalog.cluster_id.eq(int(candidate))]
            if not row.empty:
                entries = [html.H3(f"Candidate {int(candidate)} · {int(row.iloc[0].n_members):,} full members")]
                metrics = []
                for key, title in [("n_members", "Full members"), ("cluster_persistence", "Persistence"),
                            ("mean_membership_strength", "Density strength"), ("seed_jaccard_mean", "Mean seed agreement"),
                            ("direct_6d_best_jaccard", "Direct 6D agreement"), ("position_elongation", "Position elongation"),
                            ("velocity_dispersion_3d_kms", "3D velocity spread (km/s)")]:
                    value = row.iloc[0].get(key)
                    text = f"{value:.4g}" if value is not None and pd.notna(value) else "Unavailable — not recorded or not calculated"
                    metrics.append(html.Div([html.Strong(text), html.Span(title)]))
                entries.append(html.Div(metrics, className="metric-grid"))
                members = data.stars.loc[data.stars.cluster_id.eq(int(candidate))]
                physical = []
                for prefix, keys, unit in [("Median position", ["x_kpc", "y_kpc", "z_kpc"], "kpc"),
                                           ("Median velocity", ["vx_kms", "vy_kms", "vz_kms"], "km/s")]:
                    values = ", ".join(f"{members[key].median():.3f}" for key in keys)
                    physical.append(html.P(f"{prefix}: ({values}) {unit}"))
                entries.extend(physical)
                if "membership_strength" in members:
                    entries.append(html.Details([html.Summary("Density-strength distribution"),
                        html.Pre(members.membership_strength.describe().round(3).to_string())]))
                details = entries
        return *figures, count_text, details, source_status

    @app.callback(Output("active-run", "data"), Output("run-settings", "data"), Output("run-info", "children"),
                  Output("data-badge", "children"), Output("run-message", "children"), Input("run-select", "value"))
    def switch_run(key):
        try:
            selected = get_run(key)
            cap = default_cap if key == "saved" else min(len(selected.stars), selected.summary.get("config", {}).get("plot_max_stars", 20000))
            name = initial_path.name if key == "saved" else selected.summary.get("input_name", key)
            return (key, {"cap": cap, "total": len(selected.stars), "run": key},
                f"Loaded run: {name} · {len(selected.stars):,} selected stars · {len(selected.catalog):,} candidates",
                "SYNTHETIC DEMONSTRATION" if selected.summary.get("data_kind") == "synthetic_toy" else "CANDIDATE SEARCH", "")
        except (ValueError, OSError) as exc:
            return no_update, no_update, no_update, no_update, str(exc)

    @app.callback(Output("review-status", "value"), Output("review-notes", "value"), Output("review-target", "data"),
                  Output("save-review", "disabled"), Output("review-meta", "children"),
                  Output("review-status", "disabled"), Output("review-notes", "disabled"),
                  Input("candidate", "value"), Input("active-run", "data"), Input("review-revision", "data"))
    def load_review(candidate, key, revision):
        if candidate is None:
            return "Unreviewed", "", None, True, "Select a candidate to add a decision and notes.", True, True
        try:
            store = get_reviews(key)
            review = store.get(candidate)
            target = {"run": key or "saved", "candidate": str(candidate), "revision": review["revision"]}
            meta = "Saved " + review["updated_at"] + " (UTC)" if review["updated_at"] else "No saved review yet."
            return review["status"], review["notes"], target, False, meta, False, False
        except ValueError as exc:
            return "Unreviewed", "", None, True, str(exc), True, True

    @app.callback(Output("review-feedback", "children"), Output("review-revision", "data"),
                  Input("save-review", "n_clicks"), State("candidate", "value"), State("active-run", "data"),
                  State("review-target", "data"), State("review-status", "value"), State("review-notes", "value"),
                  State("review-revision", "data"), prevent_initial_call=True)
    def save_review(clicks, candidate, key, target, status, notes, revision):
        key = key or "saved"
        try:
            if not target or target.get("run") != key or target.get("candidate") != str(candidate):
                raise ValueError("Wait for this candidate’s review to load before saving")
            get_reviews(key).save(candidate, status, notes or "", target["revision"])
            return f"Saved review for candidate {candidate}: {status}.", (revision or 0) + 1
        except (ValueError, OSError, KeyError) as exc:
            return str(exc), no_update

    register_import_callbacks(app, manager, initial_path.name)
    app.result_data = result_data
    app.import_manager = manager
    return app


def normalize_source(source):
    from .preprocessing import normalize_ids
    return str(normalize_ids(pd.Series([source], dtype="string")).iloc[0])


def serve_dashboard(results, display_cap=None, host="127.0.0.1", port=8050):
    app = create_app(results, display_cap)
    app.run(host=host, port=port, debug=False, use_reloader=False)
