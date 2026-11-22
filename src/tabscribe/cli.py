import argparse
from pathlib import Path

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="tabscribe")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    tab = sub.add_parser("tab", help="draft tabs (guitar, bass, drums) from an audio file")
    tab.add_argument("audio", type=Path)
    tab.add_argument("-o", "--out", type=Path, default=Path("out"))

    watch = sub.add_parser("watch", help="live browser preview of an .atex file")
    watch.add_argument("atex", type=Path)
    watch.add_argument("-p", "--port", type=int, default=8765)
    watch.add_argument("--no-open", action="store_true", help="don't open a browser")

    args = parser.parse_args()
    if args.cmd == "tab":
        from . import alphatex, ascii_tab
        from .pipeline import run

        song = run(args.audio, args.out)
        atex = args.out / f"{args.audio.stem}.atex"
        atex.write_text(alphatex.export(song))
        (args.out / f"{args.audio.stem}.txt").write_text(ascii_tab.render(song))
        print(atex)
    elif args.cmd == "watch":
        from .watch import serve

        serve(args.atex, args.port, not args.no_open)


if __name__ == "__main__":
    main()
