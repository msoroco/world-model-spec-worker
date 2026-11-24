"""Build textual, source-hashed CPU diagnostics for the three exact cases.

Temporary captures and full-size generated FFV1 media stay in .runtime-work.
These synthetic sources never establish reviewed roadway or physical authority.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_native_capture import World, CAMERAS, control, media_factory, transform
from native_capture import capture
from original_graph import collect
from core_projection import project as project_core


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(suffix: str, scratch: Path) -> None:
    if suffix not in ('below', 'equal', 'above'):
        raise ValueError('unknown exact diagnostic case')
    case_id = ROOT.name + '__' + suffix
    world = World()
    example = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    diagnostic_road = example['files']['road.xodr']
    world.map.to_opendrive = lambda: diagnostic_road
    site = {
        'format': 'c10301-native-site-v1', 'case_id': case_id,
        'cell_id': 'C10301', 'layout': 'alley', 'control': 'access_aisle',
        'actor': 'motor_vehicle_driver', 'maneuver': 'travel',
        'diagnostic_fixture': True, 'map_name': world.map.name,
        'opendrive_sha256': hashlib.sha256(world.map.to_opendrive().encode()).hexdigest(),
        'access_aisle_source_ref': 'diagnostic aisle',
        'route_source_ref': 'diagnostic route',
        'route': [{'s_m': 10 * i, 'x_m': 10 * i, 'y_m': 0, 'z_m': 0}
                  for i in range(181)],
        'vehicle_blueprint_id': 'vehicle.diagnostic',
        'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                           'x_m': 0, 'y_m': 0, 'z_m': 1.5,
                           'pitch_deg': 0, 'yaw_deg': 0, 'roll_deg': 0}
                    for name in CAMERAS}}
    seed = scratch / ('fixture-seed-' + suffix + '-v12')
    if seed.exists():
        raise ValueError('retain prior diagnostic seed; choose fresh scratch')
    seed.mkdir(parents=True)
    site_path = seed / 'site.json'
    site_path.write_text(json.dumps(site, sort_keys=True) + '\n')
    attempt = seed / 'attempt'
    def graph_reader(world, actor, snapshot, frame, time_s):
        return collect(world, actor, snapshot, expected_frame=frame,
                       expected_time_s=snapshot.timestamp.elapsed_seconds,
                       recording_time_s=time_s)
    capture(world, site_path, attempt, case_id, 'fixture-' + suffix, 0.05,
            transform, control, diagnostic_fixture=True,
            media_factory=media_factory, graph_reader=graph_reader)
    (attempt / 'recorder_info.txt').write_text(
        'Synthetic CPU fixture recorder\nCreate 17: vehicle.diagnostic\n')
    core = seed / 'core'
    project_core(attempt, core, case_id, allow_diagnostic=True)
    media = scratch / 'video-prehash'
    for name in ('overview', 'detail', 'raw'):
        if not (media / (name + '.mkv')).is_file():
            raise ValueError('generate pinned full-profile FFV1 scratch media first')
    files = {path.name: path.read_text() for path in attempt.iterdir()
             if path.suffix in ('.json', '.jsonl', '.xodr')}
    for source in (core / 'capture').rglob('*'):
        if source.is_file():
            files[str(source.relative_to(core))] = source.read_text()
    index = json.loads(files['capture-index.json'])
    for camera in CAMERAS:
        source = media / ('overview.mkv' if camera == 'front' else 'detail.mkv')
        index['cameras'][camera]['sha256'] = sha(source)
    files['capture-index.json'] = json.dumps(index, sort_keys=True, indent=2) + '\n'
    videos = [{'path': name + '.mkv', 'frames': 900,
               'width': width, 'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in (
                  ('front', 1920, 1080), ('front_left', 1280, 720),
                  ('front_right', 1280, 720), ('rear', 1280, 720),
                  ('overview', 1920, 1080), ('approach', 1280, 720),
                  ('reference_corner', 1280, 720),
                  ('driver_reference', 1280, 720), ('raw', 3840, 1800))]
    spec = {'files': files, 'graphs': [], 'videos': videos}
    case = ROOT / 'cases' / suffix
    diagnostic = case / 'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, separators=(',', ':'),
                                     ensure_ascii=False) + '\n')
    contract = case / 'measurement-contract.json'
    recipe = {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-contract-source.json',
                     'source': str(contract.relative_to(REPO)),
                     'sha256': sha(contract)}],
        'generator': {'source': str(diagnostic.relative_to(REPO)),
                      'sha256': sha(diagnostic)}}
    (case / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    if diagnostic.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic source exceeds return limit')
    print(suffix, diagnostic.stat().st_size, sha(diagnostic))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build_diagnostics.py .runtime-work/c10301-next')
    destination = Path(sys.argv[1]).resolve()
    if REPO / '.runtime-work' not in destination.parents:
        raise ValueError('diagnostic scratch must stay under .runtime-work')
    for suffix in ('below', 'equal', 'above'):
        build(suffix, destination)
