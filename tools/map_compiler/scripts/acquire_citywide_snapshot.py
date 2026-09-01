from __future__ import annotations

import argparse
import json
from pathlib import Path

from nydrive_map_compiler.acquisition import PAGE_SIZE, build_citywide_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire deterministic NYC five-borough Roadbed/CSCL/building snapshot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--roadbed-revision", required=True, help="source data revision recorded in the snapshot")
    parser.add_argument("--centerline-revision", required=True, help="source data revision recorded in the snapshot")
    parser.add_argument("--building-revision", required=True, help="Building Footprints revision recorded in the snapshot")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    args = parser.parse_args()

    snapshot = build_citywide_snapshot(
        roadbed_revision=args.roadbed_revision,
        centerline_revision=args.centerline_revision,
        building_revision=args.building_revision,
        page_size=args.page_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} roadbed={len(snapshot['roadbed']['features'])} "
        f"centerline={len(snapshot['centerline']['features'])} "
        f"buildings={len(snapshot['buildings']['features'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
