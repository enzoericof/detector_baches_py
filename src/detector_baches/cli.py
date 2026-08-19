"""Interfaz de línea de comandos para la primera demostración vertical."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from detector_baches.geojson import convert_observations_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detector-baches",
        description="Valida observaciones y las exporta como GeoJSON.",
    )
    parser.add_argument("input", type=Path, help="Archivo JSON de observaciones")
    parser.add_argument("output", type=Path, help="Archivo GeoJSON de salida")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = convert_observations_file(args.input, args.output)
    print(f"Se exportaron {count} observaciones a {args.output}")
    return 0
