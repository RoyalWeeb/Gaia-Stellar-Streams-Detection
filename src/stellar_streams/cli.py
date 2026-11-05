import argparse
from pathlib import Path
import json
from .config import load_config


def main():
    parser = argparse.ArgumentParser(description="Gaia DR3 candidate-stream discovery")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and cluster synthetic toy observations")
    demo.add_argument("--output", default="outputs/demo")
    demo.add_argument("--config", default=None)
    demo.add_argument("--field-stars", type=int, default=3600)
    demo.add_argument("--members-per-stream", type=int, default=240)
    run = commands.add_parser("run", help="Process a local Gaia CSV or VOTable")
    run.add_argument("--input", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--config", default=None)
    run.add_argument("--data-kind", choices=["gaia_dr3", "user_supplied"], default="user_supplied")
    fetch = commands.add_parser("fetch", help="Download a cached, paged public Gaia DR3 selection")
    fetch.add_argument("--output", default="data/gaia_dr3.csv")
    fetch.add_argument("--page-size", type=int, default=10000)
    fetch.add_argument("--max-rows", type=int, default=100000, help="0 retrieves the complete selected subset")
    fetch.add_argument("--random-index-max", type=int, default=50000000,
                       help="Gaia random_index upper bound; 0 disables this sampling cut")
    fetch.add_argument("--config", default=None)
    dashboard = commands.add_parser("dashboard", help="Explore saved results, review candidates and import local data")
    dashboard.add_argument("--results", required=True)
    dashboard.add_argument("--display-cap", type=int)
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    config = load_config(getattr(args, "config", None))
    if args.command == "dashboard":
        from .dashboard import serve_dashboard
        try:
            serve_dashboard(args.results, display_cap=args.display_cap, host=args.host, port=args.port)
        except (ValueError, RuntimeError) as exc:
            parser.error(str(exc))
        return
    if args.command == "fetch":
        from .archive import fetch_gaia
        if args.random_index_max < 0:
            parser.error("random-index-max cannot be negative")
        summary = fetch_gaia(args.output, args.page_size, args.max_rows,
                             args.random_index_max or None, config)
        print(json.dumps({k: summary[k] for k in ("total_rows", "complete", "truncated", "selection_note")}, indent=2))
    else:
        from .pipeline import run_pipeline
        if args.command == "demo":
            from .synthetic import make_demo
            root = Path(args.output)
            if root.exists() and any(root.iterdir()):
                parser.error("Demo output folder must be empty; choose a new output folder")
            make_demo(root / "data", config.seed, args.field_stars, args.members_per_stream)
            run_pipeline(root / "data/demo_gaia.csv", root / "results", config,
                         truth=root / "data/demo_truth.csv", data_kind="synthetic_toy")
        else:
            run_pipeline(args.input, args.output, config, data_kind=args.data_kind)


if __name__ == "__main__":
    main()
