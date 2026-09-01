from __future__ import annotations

import argparse
from pathlib import Path

from nydrive_map_compiler.citywide import write_compiled_citywide
from nydrive_map_compiler.vertical import RasterElevationSampler


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile the NYC five-borough road world")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dem", type=Path, action="append", required=True, help="2017 NYC DEM GeoTIFF; repeat for all required tiles")
    args = parser.parse_args()

    with RasterElevationSampler(args.dem) as elevation:
        manifest = write_compiled_citywide(
            args.snapshot,
            args.output,
            elevation_sampler=elevation,
        )

    audit = manifest["citywide_audit"]
    print(
        f"compiled tiles={manifest['tile_count']} roads={manifest['input_counts']['centerline']} "
        f"roadbed={manifest['input_counts']['roadbed']} routes={len(audit['routes'])} "
        f"components={audit['topology']['component_count']} "
        f"unresolved_surfaces={audit['vertical']['unresolved_surface_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
