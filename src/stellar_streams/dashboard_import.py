"""Guided data-loading controls and callbacks, separate from candidate views."""
import json

from .config import Config
from .dashboard_jobs import LOAD_FIELDS, import_config, source_descriptor


def import_panel(html, dcc, label, initial_name):
    defaults = Config().to_dict()
    def setting(spec):
        key, title, lower, upper, step = spec
        return label(title, dcc.Input(id="load-" + key, type="number", value=defaults[key],
                                     min=lower, max=upper, step=step, debounce=True))
    return html.Section([
        html.Div([
            html.Div([html.H2("Your saved runs"), html.P("Open a saved run or prepare a new local Gaia sample.")]),
            label("Loaded results", dcc.Dropdown(id="run-select", options=[{"label": initial_name, "value": "saved"}],
                  value="saved", clearable=False, className="explorer-dropdown")),
        ], className="run-picker"),
        html.Div(id="run-message", role="status"),
        html.Details([
            html.Summary("Load Gaia data"),
            html.P("Choose your catalogue, preview the measurement and halo cuts, then create a new candidate-search run."),
            html.Div([
                label("File source", dcc.RadioItems(id="input-mode", options=[
                    {"label": " Choose a file", "value": "upload"},
                    {"label": " Use a path on this computer", "value": "path"}], value="upload", className="source-options")),
                label("Data origin", dcc.Dropdown(id="input-kind", options=[
                    {"label": "Gaia DR3 catalogue", "value": "gaia_dr3"},
                    {"label": "Other supplied observations", "value": "user_supplied"}], value="gaia_dr3", clearable=False)),
            ], className="controls"),
            html.Div([
                dcc.Upload(id="input-upload", children=html.Button("Choose Gaia file", type="button"),
                           accept=".csv,.vot,.votable,.xml", multiple=False),
                html.P("No file chosen", id="input-upload-name"),
                html.Small("CSV or VOTable. For files over 64 MiB, use a local path. VOTable parsing loads the file into memory."),
            ], id="upload-area", className="upload-area"),
            html.Div([label("Catalogue path", dcc.Input(id="input-path", type="text", value="",
                          placeholder="data/gaia_halo.csv", debounce=True)),
                      html.Small("Relative paths start in the project folder. Absolute local paths are also accepted.")],
                     id="path-area", style={"display": "none"}),
            html.H3("Selection settings"),
            html.Div([setting(spec) for spec in LOAD_FIELDS[:5]] + [
                label("When the selected sample exceeds the limit", dcc.Dropdown(id="load-sampling", options=[
                    {"label": "Stop and let me change the selection", "value": "error"},
                    {"label": "Use a reproducible uniform sample", "value": "uniform"}], value="error", clearable=False)),
            ], className="controls"),
            html.Details([html.Summary("Clustering settings"),
                          html.Div([setting(spec) for spec in LOAD_FIELDS[5:]], className="controls")]),
            html.P("Preview scans the complete file and reports actual selection counts. The distance estimate is inverse positive parallax; clustering runs in memory with a maximum of 100,000 selected stars."),
            html.Div([html.Button("Preview selection", id="preview-data", n_clicks=0, type="button"),
                      html.Button("Start processing", id="start-processing", n_clicks=0, type="button", disabled=True),
                      html.Button("Open new results", id="open-new-run", n_clicks=0, type="button", disabled=True)], className="action-row"),
            html.Div(id="import-message", role="status", className="feedback"),
            html.Progress(id="job-progress", max=5, value=0),
            html.Div("Choose a file to begin.", id="job-stage", role="status", **{"aria-live": "polite"}),
            html.Div(id="preview-summary"),
            dcc.Store(id="input-signature"), dcc.Store(id="import-job", storage_type="session"),
            dcc.Store(id="completed-job"), dcc.Interval(id="job-poll", interval=1500, n_intervals=0),
        ], className="import-wizard"),
    ], className="data-workspace")


def register_import_callbacks(app, manager, initial_name):
    from dash import Input, Output, State, ctx, no_update, html
    field_states = [State("load-" + spec[0], "value") for spec in LOAD_FIELDS]

    app.clientside_callback("""function(contents, filename, modified) {
        if (!contents) return [null, 'No file chosen'];
        return [{filename:filename, length:contents.length, modified:modified}, filename];
    }""", Output("input-signature", "data"), Output("input-upload-name", "children"),
        Input("input-upload", "contents"), State("input-upload", "filename"), State("input-upload", "last_modified"))

    @app.callback(Output("upload-area", "style"), Output("path-area", "style"), Input("input-mode", "value"))
    def source_mode(mode):
        return ({"display": "none"}, {}) if mode == "path" else ({}, {"display": "none"})

    @app.callback(Output("import-job", "data"), Output("import-message", "children"),
        Input("preview-data", "n_clicks"), Input("start-processing", "n_clicks"),
        State("import-job", "data"), State("input-mode", "value"), State("input-path", "value"),
        State("input-signature", "data"), State("input-kind", "value"), State("input-upload", "contents"),
        State("input-upload", "filename"), State("load-sampling", "value"), *field_states, prevent_initial_call=True)
    def prepare(preview_clicks, start_clicks, key, mode, path, signature, kind, contents, filename, sampling, *values):
        try:
            config = import_config(dict(zip((s[0] for s in LOAD_FIELDS), values)), sampling)
            descriptor = source_descriptor(mode, path, signature, kind)
            if ctx.triggered_id == "start-processing":
                manager.start(key, config, descriptor)
                return key, "Processing started. You can continue exploring the loaded run while it works."
            key = manager.preview(descriptor, config, contents, filename)
            return key, "Preview requested. Selection progress appears below."
        except (ValueError, OSError, TypeError) as exc:
            return no_update, str(exc)

    @app.callback(Output("job-progress", "value"), Output("job-stage", "children"), Output("preview-summary", "children"),
        Output("start-processing", "disabled"), Output("preview-data", "disabled"), Output("open-new-run", "disabled"),
        Output("completed-job", "data"), Output("run-select", "options"),
        Input("job-poll", "n_intervals"), Input("import-job", "data"), Input("input-mode", "value"),
        Input("input-path", "value"), Input("input-signature", "data"), Input("input-kind", "value"),
        Input("load-sampling", "value"), *[Input("load-" + s[0], "value") for s in LOAD_FIELDS])
    def poll(tick, key, mode, path, signature, kind, sampling, *values):
        options = [{"label": initial_name, "value": "saved"}] + [
            {"label": f"{job['filename']} · {job.get('selected_rows', 0):,} stars · {job['id'][:8]}", "value": job["id"]}
            for job in manager.completed()]
        if not key:
            return 0, "Choose a file to begin.", [], True, False, True, None, options
        try:
            state = manager.state(key)
        except ValueError as exc:
            return 0, str(exc), [], True, False, True, None, options
        busy = state["status"] in ("queued", "running")
        completed = state["status"] == "completed"
        changed = False
        try:
            config = import_config(dict(zip((s[0] for s in LOAD_FIELDS), values)), sampling)
            changed = (state["config"] != config.to_dict() or state["source"] != source_descriptor(mode, path, signature, kind))
        except (ValueError, TypeError):
            changed = True
        message = state["message"]
        if changed and state["status"] == "ready":
            message = "File or settings changed. Preview again before processing."
        if state["status"] == "failed":
            message = "Could not finish: " + message
        preview = state.get("preview") or {}
        content = [html.P("Previewed file: " + state.get("filename", "Local catalogue"))]
        if preview.get("missing_columns"):
            content.append(html.P("Required columns missing: " + ", ".join(preview["missing_columns"]), className="error-text"))
        counts = preview.get("counts")
        if counts:
            content.append(html.Div([html.Div([html.Strong(f"{counts[key]:,}"), html.Span(title)]) for key, title in (
                ("raw_rows", "Rows read"), ("quality_rows", "Pass quality cuts"),
                ("halo_rows", "Pass halo cut"), ("selected_rows", "Selected for fitting"))], className="metric-grid"))
            content.append(html.P(f"Rejected by quality: {counts['quality_rejected']:,}. Rejected by halo cut: {counts['non_halo_rejected']:,}. " +
                ("The selected count uses a reproducible uniform sample." if counts["sampled"] and state["config"]["sampling"] == "uniform"
                 else "The full eligible sample is retained." if not counts["sampled"] else "The star limit is exceeded; processing is blocked.")))
        if preview.get("columns"):
            content.append(html.Details([html.Summary("Checked columns and first selected rows"),
                html.P(", ".join(preview["columns"])), html.Pre(json.dumps(
                    preview.get("selected_preview", preview.get("sample_rows", [])), indent=2))]))
        if completed:
            content.append(html.P("Saved results: " + str(manager.result_path(key)), className="saved-path"))
        can_run = state["status"] == "ready" and preview.get("can_run", False) and not changed
        return state.get("stage", 0), message, content, not can_run, busy, not completed, key if completed else None, options

    @app.callback(Output("run-select", "value"), Input("open-new-run", "n_clicks"),
                  State("completed-job", "data"), prevent_initial_call=True)
    def open_completed(clicks, key):
        if key:
            try:
                manager.result_path(key)
                return key
            except ValueError:
                pass
        return no_update
