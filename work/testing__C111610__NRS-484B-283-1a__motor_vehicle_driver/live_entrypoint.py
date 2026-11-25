"""Operator entrypoint for one source-reviewed original crosswalk attempt.

This intentionally requires site and exception packets supplied by local
review. It does not connect to CARLA at import time or accept nominal scene
coordinates as proof of map geometry.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def run(*, host, port, scene, site, exception, output):
    import carla

    from carla_scene_factory import make_scene_factory
    from live_crosswalk import run as capture

    client = carla.Client(host, port)
    client.set_timeout(30.0)
    return capture(client, Path(scene), Path(site), Path(exception),
                   Path(output), make_scene_factory(carla))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--exception", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run(**vars(args))
    print(result["source_index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
