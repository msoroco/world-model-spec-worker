"""Stage reviewed-source bundles for canonical assignment-root publication.

Staging does not review site facts, publish a manifest, or claim delivery readiness.
The staged files must be installed under this assignment before runtime.py
compatibility, whose pinned resolver requires an assignment-root manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from parking_pose import REQUESTS, SWEEP_REQUESTS
from source_review import validate


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_fixture_spec(original, scene, xodr):
    """Rebase synthetic telemetry to the sealed scene, retaining diagnostic scope."""
    spec = json.loads(json.dumps(original))
    files = spec['files']
    pose = scene['target_pose']
    corners = pose['target_body_vertices_xy_m']
    forward = pose['target_forward_xy']
    center = [sum(point[axis] for point in corners) / 4 for axis in (0, 1)]
    heading = math.degrees(math.atan2(forward[1], forward[0]))
    def rows(name):
        return [json.loads(line) for line in files[name].splitlines()]
    def write_rows(name, values):
        files[name] = ''.join(json.dumps(value, allow_nan=False) + '\n' for value in values)
    history = rows('parking-history.jsonl')
    for row in history:
        row['body_vertices_xy_m'] = corners
        row['vehicle_forward_xy'] = forward
    write_rows('parking-history.jsonl', history)
    trace = rows('trace.jsonl')
    for row in trace:
        row['position'] = {'x': center[0], 'y': center[1], 'z': 0.0}
        row['position_m'] = [center[0], center[1], 0.0]
        row['heading_deg'] = heading
        row['velocity_mps'] = [forward[0] * row['speed_mps'],
                               forward[1] * row['speed_mps'], 0.0]
    write_rows('trace.jsonl', trace)
    evidence = rows('capture/evidence.jsonl')
    for row in evidence:
        row['ego']['body_vertices_m'] = [[x, y, z] for x, y in corners
                                         for z in (0.0, 1.5)]
        row['ego']['heading_deg'] = heading
        row['ego']['position_m'] = [center[0], center[1], 0.0]
    write_rows('capture/evidence.jsonl', evidence)
    files['road.xodr'] = xodr
    files['capture/recorder_info.txt'] = (
        'Create 7: vehicle.tesla.model3 (parking diagnostic) at (' +
        ', '.join(str(value) for value in (center[0], center[1], 0)) + ')\n')
    capture = json.loads(files['capture/manifest.json'])
    capture['sources']['road.xodr'] = hashlib.sha256(xodr.encode()).hexdigest()
    capture['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(capture) + '\n'
    return spec


def stage(rebound_dir, output_dir):
    rebound = Path(rebound_dir).resolve()
    output = Path(output_dir).resolve()
    scratch = (REPO / '.runtime-work').resolve()
    if (not rebound.is_relative_to(scratch) or not output.is_relative_to(scratch)
            or output.exists() or rebound == output):
        raise ValueError('rebound and fresh staging output must be under .runtime-work')
    source = json.loads((rebound / 'rebound-manifest.json').read_text())
    manifest = json.loads((rebound / 'execution-manifest.json').read_text())
    expected = {ROOT.name + '__' + name for name in (*REQUESTS, *SWEEP_REQUESTS)}
    if (source.get('assignment_id') != ROOT.name or
            source.get('preparation_status') != 'review_and_cpu_proofs_pending' or
            {item['case_id'] for item in source['cases']} != expected or
            {item['case_id'] for item in manifest['cases']} != expected):
        raise ValueError('rebound exact-case identity or status differs')
    source_cases = {item['case_id']: item for item in source['cases']}
    packet_hashes = source.get('packet_sha256', {})
    if set(packet_hashes) != {'park', 'stand'}:
        raise ValueError('separate retained activity packet hashes required')
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='c150041-canonical-stage-', dir=output.parent))
    try:
        mapping = []
        for entry in manifest['cases']:
            case_id = entry['case_id']
            activity = source_cases[case_id]['activity']
            if activity not in packet_hashes:
                raise ValueError('rebound activity lacks a packet hash')
            variants = {item['id']: item for item in source_cases[case_id]['variants']}
            if set(variants) != {'primary', 'fallback1'} or len(entry.get('candidates', [])) != 1:
                raise ValueError('exact primary and fallback1 required')
            primary_bundle = json.loads((rebound / variants['primary']['construction']).read_text())
            original_files = {item['path']: item['content'] for item in primary_bundle['files']}
            packet = json.loads(original_files['reviewed-context.json'])
            fixture_dir = (Path('diagnostic') / 'reviewed' /
                           packet_hashes[activity][:16] /
                           case_id.removeprefix(ROOT.name + '__'))
            reviewed_names = ['reviewed-context.json'] + [
                descriptor['path'] for descriptor in packet['sources'].values()]
            fixture_sources = []
            for name in reviewed_names:
                if name not in original_files:
                    raise ValueError('reviewed original source absent from rebound bundle: ' + name)
                retained = fixture_dir / 'source-files' / name
                retained_path = staged / retained
                retained_path.parent.mkdir(parents=True, exist_ok=True)
                retained_path.write_text(original_files[name])
                fixture_sources.append({'path': name,
                                        'source': (Path('work') / ROOT.name / retained).as_posix(),
                                        'sha256': sha(retained_path)})
            original_recipe = json.loads((ROOT / entry['fixture_recipe'].removeprefix(
                'work/' + ROOT.name + '/')).read_text())
            original_spec = json.loads((REPO / original_recipe['generator']['source']).read_text())
            scene = json.loads(original_files['scene.json'])
            xodr = original_files[packet['sources']['roadway']['path']]
            spec_path = fixture_dir / 'fixture-spec.json'
            (staged / spec_path).write_text(json.dumps(
                reviewed_fixture_spec(original_spec, scene, xodr), indent=2) + '\n')
            recipe = {'format': 'worker-fixture-recipe',
                      'sources': fixture_sources,
                      'generator': {'source': (Path('work') / ROOT.name / spec_path).as_posix(),
                                    'sha256': sha(staged / spec_path)}}
            fixture_recipe = fixture_dir / 'fixture-recipe.json'
            (staged / fixture_recipe).write_text(json.dumps(recipe, indent=2) + '\n')
            entry['fixture_recipe'] = (Path('work') / ROOT.name / fixture_recipe).as_posix()
            for candidate_id, selected in (('primary', entry),
                                           ('fallback1', entry['candidates'][0])):
                variant = variants[candidate_id]
                construction = rebound / variant['construction']
                if (not construction.resolve().is_relative_to(rebound) or
                        sha(construction) != variant['construction_sha256'] or
                        selected['construction_sha256'] != variant['construction_sha256'] or
                        variant['source_packet_sha256'] != packet_hashes[activity]):
                    raise ValueError('rebound construction or packet seal differs')
                bundle = json.loads(construction.read_text())
                files = {item['path']: item['content'] for item in bundle['files']}
                config = json.loads(files['config.json'])
                scene = json.loads(files['scene.json'])
                if (bundle['case_id'] != case_id or scene['case_id'] != case_id or
                        scene['source_packet_sha256'] != packet_hashes[activity] or
                        config['selected_case_id'] != case_id or
                        config['reviewed_source_packet'] != {
                            'path': 'reviewed-context.json',
                            'sha256': packet_hashes[activity],
                            'source_kind': 'retained_reviewed_native_site_packet'}):
                    raise ValueError('rebound bundle identity or source packet differs')
                relative = (Path('diagnostic') / 'reviewed' /
                            packet_hashes[activity][:16] / case_id.removeprefix(ROOT.name + '__') /
                            (candidate_id + '.json'))
                destination = staged / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                bundle['files'] = [item for item in bundle['files']
                                   if item['path'] not in reviewed_names]
                destination.write_text(json.dumps(bundle, indent=2) + '\n')
                selected['construction'] = relative.as_posix()
                selected['construction_sha256'] = sha(destination)
                mapping.append({'case_id': case_id, 'candidate_id': candidate_id,
                                'path': relative.as_posix(), 'sha256': sha(destination)})
            for obsolete in ('offline', 'compatibility', 'negative', 'physical_preparation',
                             'post_capture', 'delivery_acceptance', 'acquisition', 'native_handoff'):
                if obsolete in entry:
                    raise ValueError('rebound manifest carries stale proof: ' + obsolete)
            entry['acquisition'] = {
                name: {
                    'entrypoint': 'parking_native_capture.py',
                    'method': 'capture_frame',
                    'evidence': 'Original vehicle bounding-box vertices, forward vector, velocity and applied control at each Native world tick in parking-history.jsonl',
                }
                for name in ('body_vertices_xy_m', 'vehicle_forward_xy',
                             'speed_m_s', 'control')
            }
            entry['acquisition']['camera_frame_map'] = {
                'entrypoint': 'parking_tick_capture.py',
                'method': 'capture_ticks',
                'evidence': 'Original world frame and timestamp joined to all four camera source names in camera-frame-map.jsonl',
            }
            if case_id.split('__')[-1] in SWEEP_REQUESTS:
                entry['acquisition']['parallel_deviation_deg'] = {
                    'entrypoint': 'parking_analysis.py', 'method': 'analyze',
                    'evidence': 'Original saved body axis measured against source-reviewed road edge in channels/parallel_deviation_deg.jsonl',
                }
            for obsolete in ('offline', 'compatibility'):
                if obsolete in entry['candidates'][0]:
                    raise ValueError('rebound candidate carries stale proof: ' + obsolete)
        (staged / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staged / 'stage-receipt.json').write_text(json.dumps({
            'format': 'c150041-canonical-stage-v1', 'assignment_id': ROOT.name,
            'status': 'review_and_cpu_proofs_pending',
            'packet_sha256': packet_hashes, 'constructions': mapping,
            'fixture_paths': sorted(str(path.relative_to(staged)) for path in
                                    staged.rglob('fixture-recipe.json')),
            'artifacts': [{'path': path.relative_to(staged).as_posix(),
                           'sha256': sha(path)} for path in sorted(staged.rglob('*'))
                          if path.is_file() and path.name != 'execution-manifest.json'],
            'manifest_sha256': sha(staged / 'execution-manifest.json'),
            'original_review_claimed': False, 'delivery_ready_claimed': False,
        }, indent=2) + '\n')
        staged.rename(output)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return output / 'stage-receipt.json'


def install(staged_dir, park_packet, stand_packet, target=ROOT):
    """Install source-bound constructions, then manifest; proofs remain pending."""
    staged = Path(staged_dir).resolve()
    target = Path(target).resolve()
    if not staged.is_relative_to((REPO / '.runtime-work').resolve()):
        raise ValueError('canonical stage must be under .runtime-work')
    receipt = json.loads((staged / 'stage-receipt.json').read_text())
    manifest_path = staged / 'execution-manifest.json'
    if (receipt.get('format') != 'c150041-canonical-stage-v1' or
            receipt.get('assignment_id') != ROOT.name or
            receipt.get('status') != 'review_and_cpu_proofs_pending' or
            receipt.get('manifest_sha256') != sha(manifest_path) or
            receipt.get('original_review_claimed') is not False or
            receipt.get('delivery_ready_claimed') is not False):
        raise ValueError('canonical stage receipt differs')
    for activity, packet in (('park', park_packet), ('stand', stand_packet)):
        packet = Path(packet).resolve()
        validate(packet, source_root=packet.parent)
        if sha(packet) != receipt['packet_sha256'][activity]:
            raise ValueError('retained reviewed packet differs from canonical stage')
    manifest = json.loads(manifest_path.read_text())
    expected = {ROOT.name + '__' + name for name in (*REQUESTS, *SWEEP_REQUESTS)}
    if (manifest.get('assignment_id') != ROOT.name or
            manifest.get('runtime_manifest_sha256') != sha(REPO / 'runtime' / 'SOURCE-MANIFEST.json') or
            {entry['case_id'] for entry in manifest['cases']} != expected or
            len(receipt['constructions']) != 32):
        raise ValueError('canonical staged exact-case inventory differs')
    declared = {(entry['case_id'], entry['candidate_id']): entry
                for entry in receipt['constructions']}
    if len(declared) != 32:
        raise ValueError('duplicate staged construction')
    for entry in manifest['cases']:
        for candidate_id, selected in (('primary', entry),
                                       ('fallback1', entry['candidates'][0])):
            row = declared[(entry['case_id'], candidate_id)]
            if (selected['construction'] != row['path'] or
                    selected['construction_sha256'] != row['sha256'] or
                    not (staged / row['path']).resolve().is_relative_to(staged) or
                    sha(staged / row['path']) != row['sha256']):
                raise ValueError('staged construction differs from manifest')
    artifacts = receipt.get('artifacts', [])
    if not artifacts or len({row['path'] for row in artifacts}) != len(artifacts):
        raise ValueError('canonical stage artifact inventory missing or duplicated')
    for row in artifacts:
        source = staged / row['path']
        destination = target / row['path']
        if not source.resolve().is_relative_to(staged) or sha(source) != row['sha256']:
            raise ValueError('staged artifact changed')
        if not destination.resolve().is_relative_to(target):
            raise ValueError('staged artifact destination escapes assignment')
        if destination.exists() and sha(destination) != row['sha256']:
            raise ValueError('published construction path has different bytes')
    # Install the sealed bundles and fixture inputs before replacing the manifest, so interruption
    # cannot leave a new manifest pointing to absent bundles.
    for row in artifacts:
        source = staged / row['path']
        destination = target / row['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        with tempfile.NamedTemporaryFile(dir=REPO / '.runtime-work', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(source.read_bytes())
        os.replace(temporary, destination)
    destination = target / 'execution-manifest.json'
    with tempfile.NamedTemporaryFile(dir=REPO / '.runtime-work', delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(manifest_path.read_bytes())
    os.replace(temporary, destination)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebound-dir')
    parser.add_argument('--output-dir')
    parser.add_argument('--install-stage')
    parser.add_argument('--park-packet')
    parser.add_argument('--stand-packet')
    args = parser.parse_args()
    if args.install_stage:
        if not args.park_packet or not args.stand_packet:
            parser.error('--install-stage requires --park-packet and --stand-packet')
        print(install(args.install_stage, args.park_packet, args.stand_packet))
    else:
        if not args.rebound_dir or not args.output_dir:
            parser.error('staging requires --rebound-dir and --output-dir')
        print(stage(args.rebound_dir, args.output_dir))


if __name__ == '__main__':
    main()
