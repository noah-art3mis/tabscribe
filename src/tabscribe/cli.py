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
    tab.add_argument("--no-media", action="store_true",
                     help="don't copy the recording and stems next to the tab")

    watch = sub.add_parser("watch", help="open one .atex file in the web app (live reload)")
    watch.add_argument("atex", type=Path)
    watch.add_argument("-p", "--port", type=int, default=8765)
    watch.add_argument("--no-open", action="store_true", help="don't open a browser")

    stages = sub.add_parser("stages", help="show which adapter fills each stage")
    stages.add_argument("-c", "--config", type=Path)

    ev = sub.add_parser("eval", help="score a pipeline config on reference tabs")
    ev.add_argument("-c", "--config", type=Path,
                    help="adapters to test (default: real models, perfect stems)")
    ev.add_argument("--cases", type=Path, default=Path("evals/cases"))
    ev.add_argument("--only", nargs="*", help="case names to run (default: all)")
    ev.add_argument("-o", "--out", type=Path, default=Path("out/evals"))
    ev.add_argument("--seed", type=int, default=0, help="seed for timing/velocity variation")

    web = sub.add_parser("web", help="open the web app on a folder of songs")
    web.add_argument("library", type=Path, nargs="?", default=Path("songs"),
                     help="folder of .atex files (default: ./songs)")
    web.add_argument("-p", "--port", type=int, default=8765)
    web.add_argument("-c", "--config", type=Path, help="pipeline config for transcription")
    web.add_argument("--no-open", action="store_true", help="don't open a browser")

    render = sub.add_parser("render", help="convert an .atex file to plain-text tab")
    render.add_argument("atex", type=Path)

    args = parser.parse_args()
    if args.cmd == "tab":
        from .application.config import build_pipeline, build_writers, load_config
        from .application.inspect import stage_dumper
        from .domain import AudioRef

        from .library import save_media

        config = load_config(args.config)
        pipeline = build_pipeline(config)
        dump = stage_dumper(args.out / "stages") if args.inspect else None
        outputs: dict = {}

        def observe(stage, output):
            outputs[stage] = output
            if dump:
                dump(stage, output)

        song = pipeline.run(AudioRef(args.audio), args.out / ".work" / args.audio.stem,
                            observe=observe)
        for writer in build_writers(config):
            path = args.out / f"{args.audio.stem}.{writer.extension}"
            path.write_text(writer.write(song))
            print(path)
        if not args.no_media and args.audio.exists():
            print(save_media(args.out, args.audio.stem, args.audio, outputs.get("3_stems") or {}))
    elif args.cmd == "watch":
        from .web.server import serve as serve_web

        serve_web(args.atex.parent, args.port, open_browser=not args.no_open, song=args.atex.stem)
    elif args.cmd == "web":
        from .web.server import serve as serve_web

        serve_web(args.library, args.port, args.config, not args.no_open)
    elif args.cmd == "eval":
        from .evals.run import main as run_eval

        run_eval(args.cases, args.out, args.config, args.only, args.seed)
    elif args.cmd == "render":
        from .adapters.notation.alphatex_reader import AlphaTexReader
        from .adapters.notation.ascii_tab import AsciiTabWriter

        print(AsciiTabWriter().write(AlphaTexReader().read_file(args.atex)), end="")
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
