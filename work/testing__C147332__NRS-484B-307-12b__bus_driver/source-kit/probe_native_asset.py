"""Probe a locally imported CARLA lane-signal blueprint before source review.

An attribute readback is a software check. A physical attempt must still inspect
the rendered red X, device facing, and official design in original camera pixels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def probe(library, blueprint_id: str, attribute: str = "display_state",
          value: str = "red_x") -> dict:
    if not blueprint_id or not blueprint_id.startswith("static."):
        raise ValueError("exact imported static signal blueprint ID required")
    try:
        blueprint = library.find(blueprint_id)
    except (KeyError, RuntimeError, IndexError) as error:
        raise ValueError("exact imported signal blueprint unavailable") from error
    if blueprint is None or not blueprint.has_attribute(attribute):
        raise ValueError("exact imported signal display attribute unavailable")
    attr = blueprint.get_attribute(attribute)
    if hasattr(attr, "is_modifiable") and not attr.is_modifiable:
        raise ValueError("signal display attribute is not modifiable")
    values = getattr(attr, "recommended_values", None)
    if values and value not in [str(v) for v in values]:
        raise ValueError("red-X value is not an allowed display state")
    blueprint.set_attribute(attribute, value)
    if str(blueprint.get_attribute(attribute)) != value:
        raise ValueError("red-X state did not read back on imported blueprint")
    return {"blueprint_id": blueprint_id, "attribute": attribute, "red_x_value": value,
            "blueprint_readback": True, "rendered_pixels_reviewed": False,
            "official_device_design_reviewed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import carla  # Only the local CARLA operator needs this dependency.
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    receipt = probe(client.get_world().get_blueprint_library(), args.blueprint_id)
    if args.output.exists():
        raise ValueError("Native asset probe receipt already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
