"""Run one exact C111304 Native attempt from independently reviewed sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from carla_adapter import CarlaEncounterAdapter
from encounter import CASES, build_case
from native_acquisition import capture
from site_binding import bind_world_site


def run(world, carla, case_id: str, site_path: Path, access_source: Path,
        access_review: Path, camera_plan_path: Path, output: Path):
    matches = [case for case in CASES if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError('unknown exact C111304 case')
    case = matches[0]
    if not output.is_dir():
        raise ValueError('existing Native attempt directory required')
    if any((output / name).exists() for name in
           ('site.json', 'access-source.txt', 'access-review.json',
            'camera-plan.json', 'native-receipt.json', 'original-history.jsonl')):
        raise ValueError('Native attempt already contains source or acquisition files')
    site = bind_world_site(world, site_path, access_source, access_review,
                           camera_plan_path, case)
    camera_plan = json.loads(camera_plan_path.read_text(encoding='utf-8'))
    adapter = CarlaEncounterAdapter(world, carla, site, camera_plan)
    try:
        adapter.start()
        actors = build_case(adapter, site, case)
        adapter.start_cameras(actors['ego'], output)
        for source, name in ((site_path, 'site.json'),
                             (access_source, 'access-source.txt'),
                             (access_review, 'access-review.json'),
                             (camera_plan_path, 'camera-plan.json')):
            shutil.copyfile(source, output / name)
        return capture(adapter, actors, case, site, output)
    finally:
        adapter.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=[case.case_id for case in CASES])
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--access-source', type=Path, required=True)
    parser.add_argument('--access-review', type=Path, required=True)
    parser.add_argument('--camera-plan', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    import carla  # CARLA exists only in the authorized local Native environment.
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    receipt = run(client.get_world(), carla, args.case, args.site,
                  args.access_source, args.access_review, args.camera_plan,
                  args.output_dir)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
