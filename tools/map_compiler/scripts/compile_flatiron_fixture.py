from __future__ import annotations

import argparse
from pathlib import Path

from nydrive_map_compiler.fixture import write_compiled_fixture

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "fixtures" / "flatiron" / "source_snapshot.json"
DEFAULT_OUTPUT = ROOT / "fixtures" / "flatiron" / "compiled"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile the checked-in Flatiron NYC source snapshot into 256 m runtime tiles.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = write_compiled_fixture(args.source, args.output)
    print(
        f"compiled {manifest['name']}: {manifest['input_counts']['roadbed']} roadbeds, "
        f"{manifest['input_counts']['centerline']} centerlines -> {manifest['tile_count']} tiles"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
