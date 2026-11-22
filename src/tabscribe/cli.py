import argparse
from pathlib import Path

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="tabscribe")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    tab = sub.add_parser("tab", help="transcribe an audio file into tabs")
    tab.add_argument("audio", type=Path)
    tab.add_argument("-o", "--out", type=Path, default=Path("out"))
    tab.add_argument("-c", "--config", type=Path, help="TOML file choosing adapters per stage")
    tab.add_argument("--inspect", action="store_true",
                     help="also save every stage's output as JSON in <out>/stages/")

    watch = sub.add_parser("watch", help="live browser preview of an .atex file")
    watch.add_argument("atex", type=Path)
    watch.add_argument("-p", "--port", type=int, default=8765)
    watch.add_argument("--no-open", action="store_true", help="don't open a browser")

    stages = sub.add_parser("stages", help="show which adapter fills each stage")
    stages.add_argument("-c", "--config", type=Path)

    args = parser.parse_args()
    if args.cmd == "tab":
        from .application.config import build_pipeline, build_writers, load_config
        from .application.inspect import stage_dumper
        from .domain import AudioRef

        config = load_config(args.config)
        pipeline = build_pipeline(config)
        observe = stage_dumper(args.out / "stages") if args.inspect else None
        song = pipeline.run(AudioRef(args.audio), args.out / "work", observe=observe)
        for writer in build_writers(config):
            path = args.out / f"{args.audio.stem}.{writer.extension}"
            path.write_text(writer.write(song))
            print(path)
    elif args.cmd == "watch":
        from .watch import serve

        serve(args.atex, args.port, not args.no_open)
    elif args.cmd == "stages":
        from .application.config import ADAPTERS, load_config

        config = load_config(args.config)
        for stage, name in config["stages"].items():
            names = name if isinstance(name, list) else [name]
            shown = ", ".join(f"{n} ({ADAPTERS.get(n, n)})" for n in names) or "(none)"
            print(f"{stage:16} {shown}")
        print(f"{'instruments':16} {', '.join(config['instruments'])}")
        print(f"{'writers':16} {', '.join(config['writers'])}")


if __name__ == "__main__":
    main()
