import argparse
from pathlib import Path

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="tabscribe")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    tab = sub.add_parser("tab", help="draft a guitar tab from an audio file")
    tab.add_argument("audio", type=Path)
    tab.add_argument("-o", "--out", type=Path, default=Path("out"))

    args = parser.parse_args()
    if args.cmd == "tab":
        from .pipeline import run

        print(run(args.audio, args.out))


if __name__ == "__main__":
    main()
