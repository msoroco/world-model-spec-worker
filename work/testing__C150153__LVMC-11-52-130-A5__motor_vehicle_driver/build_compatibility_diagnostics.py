"""Build exact synthetic 900-frame fixtures for pinned software compatibility.

These packets and pixels establish no original municipal site or physical result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'tests'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from test_independent_delivery_audit import DeliveryAuditTests
from build_source_bound_bundles import generate
from worker_exchange.fixture_generator import generate as generate_assets

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def encoded(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    scratch = ROOT / '.runtime-work/c150153-compatibility-build'
    scratch.mkdir(parents=True, exist_ok=True)
    video_spec = [{'path': name + '.mkv', 'frames': 900,
                   'width': 1920 if name == 'overview' else 1280,
                   'height': 1080 if name == 'overview' else 720,
                   'fps': 20, 'color': 'black'} for name in CAMERAS]
    video_root = scratch / 'video-hash-source'
    if video_root.exists():
        shutil.rmtree(video_root)
    video_root.mkdir()
    generated_hashes = generate_assets({'files': {}, 'graphs': [], 'videos': video_spec}, video_root)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest_entries = []
    for case in plan['cases']:
        case_id = case['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        folder = HERE / 'cases' / kind
        with TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            attempt, packet, source_root, seal = DeliveryAuditTests().fixture(root, kind)
            reviewed = attempt / 'reviewed-site'
            reviewed.mkdir()
            shutil.copy2(packet, reviewed / 'packet.json')
            shutil.copytree(source_root, reviewed / 'sources')
            rows = [json.loads(line) for line in (attempt / 'history.jsonl').read_text().splitlines()]
            trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
            for row in trace:
                row['heading_deg'] = 0.0
                row['speed_mph'] = row['speed_mps'] / .44704
                x, y, z = row['position_m']
                row['position'] = {'x': x, 'y': y, 'z': z}
                row['velocity_mps'] = [0.0, 0.0, 0.0]
                row['control'] = {}
            (attempt / 'trace.jsonl').write_text(''.join(encoded(row) for row in trace))
            seal['sources']['trace.jsonl'] = sha(attempt / 'trace.jsonl')
            for name in CAMERAS:
                seal['sources'][name + '.mkv'] = generated_hashes[name + '.mkv']
            (attempt / 'capture-seal.json').write_text(encoded(seal))
            source_dir = folder / 'fixture-sources'
            if source_dir.exists():
                shutil.rmtree(source_dir)
            source_dir.mkdir()
            sources = []
            for path in attempt.rglob('*'):
                if not path.is_file() or path.suffix == '.mkv':
                    continue
                relative = str(path.relative_to(attempt))
                target = source_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                sources.append({'path': relative, 'source': str(target.relative_to(ROOT)),
                                'sha256': sha(target)})
            events, frames, graphs = [], [], []
            for row in rows:
                number, time_s = row['original_frame'], row['time_s']
                position = row['ego_position_m']
                x, y, z = position
                body = [[x + dx, y + dy, z + dz]
                        for dx in (-2.0, 2.0) for dy in (-0.9, 0.9)
                        for dz in (-0.5, 0.5)]
                observation = {'frame': number, 'time_s': time_s,
                               'participants': [], 'map_context': {}}
                events.append({'actor_id': 17, 'original_frame': number,
                               'replay_frame': number, 'recording_time_s': time_s,
                               'replay_simulation_time_s': time_s,
                               'ego': {'position_m': position, 'heading_deg': 0.0,
                                       'speed_mps': row['ego_speed_mps'],
                                       'speed_provenance': 'synthetic_native_sample',
                                       'body_vertices_m': body},
                               'world': {'weather': {}},
                               'original_observations': observation})
                graph_path = f'graphs/base/{number:08d}.adapter.json'
                frames.append({'frame': number, 'simulation_time': time_s,
                               'adapter_graph': graph_path})
                graphs.append({'path': 'capture/native/' + graph_path,
                               'attributes': {'frame': number,
                                              'observed_evidence': observation,
                                              'time_s': time_s},
                               'nodes': [], 'edges': []})
            road = json.loads((ROOT / 'runtime/fixtures/example.json').read_text())['files']['road.xodr']
            generated = {'acquisition-provenance.json': encoded({
                             'diagnostic_fixture': True,
                             'provenance_kind': 'synthetic_fixture'}),
                         'fixture-provenance.json': encoded({
                             'diagnostic_fixture': True,
                             'scope': 'synthetic elevator protocol; no original pixels'}),
                         'road.xodr': road,
                         'capture/evidence.jsonl': ''.join(encoded(v) for v in events),
                         'capture/native/frames.jsonl': ''.join(encoded(v) for v in frames),
                         'capture/recorder_info.txt': 'Create 17: vehicle.diagnostic.ego (0) at (0, 0, 0)\n'}
            generated['capture/manifest.json'] = encoded({
                'acquisition': 'diagnostic_fixture', 'case_id': case_id,
                'frames': 900, 'extraction_confirmed': True,
                'sources': {'road.xodr': hashlib.sha256(road.encode()).hexdigest(),
                            'trace.jsonl': sha(attempt / 'trace.jsonl')},
                'required_observations': [], 'status': 'draft'})
            spec_path = folder / 'diagnostic-compatibility.json'
            spec_path.write_text(encoded({'files': generated, 'graphs': graphs,
                                          'videos': video_spec}))
            recipe_path = folder / 'fixture-recipe.json'
            recipe_path.write_text(encoded({
                'format': 'worker-fixture-recipe',
                'generator': {'source': str(spec_path.relative_to(ROOT)),
                              'sha256': sha(spec_path)},
                'sources': sorted(sources, key=lambda v: v['path'])}))
            if max(spec_path.stat().st_size, recipe_path.stat().st_size,
                   *(p.stat().st_size for p in source_dir.rglob('*') if p.is_file())) > 2 * 1024 * 1024:
                raise ValueError('Synthetic diagnostic source exceeds returned file limit')
            draft = scratch / ('draft-' + kind)
            if draft.exists():
                shutil.rmtree(draft)
            index = generate(packet, source_root, 4.0, draft)
            entry = next(v for v in index['cases'] if v['case_id'] == case_id)
            construction = folder / 'source-bound-diagnostic-construction.json'
            shutil.copy2(draft / entry['construction'], construction)
            entry.update(construction=str(construction.relative_to(HERE)),
                         measurement_contract=str((folder / 'measurement-contract.json').relative_to(HERE)),
                         fixture_recipe=str(recipe_path.relative_to(ROOT)),
                         diagnostic_only=True)
            manifest_entries.append(entry)
            print(kind, 'spec_bytes', spec_path.stat().st_size)
    manifest = {'assignment_id': HERE.name,
                'status': 'synthetic_diagnostic_only_unselected_original_capture_pending',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': manifest_entries}
    (HERE / 'execution-manifest.source-bound-diagnostic.json').write_text(
        json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
