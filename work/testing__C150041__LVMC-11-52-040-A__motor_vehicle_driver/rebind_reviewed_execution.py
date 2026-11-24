"""Build exact Native attempt bundles from two retained reviewed site packets.

The output is scratch preparation, not evidence of Native motion or delivery.
The caller must review the source packets independently before using them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from bind_reviewed_site import bind
from parking_pose import REQUESTS
from parking_scene import build
from source_review import validate


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rebind(park_packet, stand_packet, output_dir):
    output = Path(output_dir).resolve()
    scratch = (REPO / '.runtime-work').resolve()
    if not output.is_relative_to(scratch) or output.exists():
        raise ValueError('fresh rebind output under .runtime-work required')
    packets = {'park': Path(park_packet).resolve(),
               'stand': Path(stand_packet).resolve()}
    binding = bind(packets['park'], packets['stand'])
    source_files = {}
    for activity, packet_path in packets.items():
        validate(packet_path, source_root=packet_path.parent)
        packet = json.loads(packet_path.read_text())
        files = {'reviewed-context.json': packet_path.read_text()}
        for descriptor in packet['sources'].values():
            relative = Path(descriptor['path'])
            if (relative.is_absolute() or '..' in relative.parts or
                    relative.parts[0] != 'reviewed_sources'):
                raise ValueError('reviewed source path must stay under reviewed_sources')
            source = packet_path.parent / relative
            if sha(source) != descriptor['sha256']:
                raise ValueError('retained reviewed source hash changed')
            files[relative.as_posix()] = source.read_text()
        source_files[activity] = files
    original = json.loads((ROOT / 'execution-manifest.json').read_text())
    originals = {entry['case_id']: entry for entry in original['cases']}
    expected = {ROOT.name + '__' + suffix for suffix in REQUESTS}
    if set(originals) != expected:
        raise ValueError('six exact delivery template cases required')
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='c150041-rebind-', dir=output.parent))
    try:
        entries = []
        runtime_entries = []
        for suffix, (activity, _, _) in REQUESTS.items():
            case_id = ROOT.name + '__' + suffix
            template = originals[case_id]
            variants = []
            for candidate_id, item, distance in (
                    ('primary', template, 8.0),
                    ('fallback1', template['candidates'][0], 6.0)):
                source = ROOT / item['construction']
                if sha(source) != item['construction_sha256']:
                    raise ValueError('delivery construction template changed')
                package = json.loads(source.read_text())
                scene = build(packets[activity], packets[activity].parent,
                              suffix, approach_distance_m=distance)
                if (scene['case_id'] != case_id or
                        scene['source_packet_sha256'] != binding['packet_sha256'][activity]):
                    raise ValueError('reviewed scene and packet differ')
                files = {row['path']: row for row in package['files']}
                if set(files).intersection(source_files[activity]):
                    raise ValueError('template embeds a reviewed source')
                config = json.loads(files['config.json']['content'])
                if config['selected_case_id'] != case_id:
                    raise ValueError('template config case differs')
                files['scene.json']['content'] = json.dumps(scene, indent=2) + '\n'
                files['parking_runner.py']['content'] = (ROOT / 'parking_runner.py').read_text()
                config['reviewed_source_packet'] = {
                    'path': 'reviewed-context.json',
                    'sha256': binding['packet_sha256'][activity],
                    'source_kind': 'retained_reviewed_native_site_packet',
                }
                files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
                files['runner.py']['content'] = (
                    '"""Reviewed-source Native parking entrypoint."""\n'
                    'import sys\n'
                    'from parking_runner import main\n'
                    'if __name__ == "__main__":\n'
                    '    sys.argv.extend(["--packet", "reviewed-context.json", '
                    '"--source-root", ".", "--case", "' + suffix + '", '
                    '"--approach-distance-m", "' + str(distance) + '"])\n'
                    '    main()\n')
                files['tests/test_delivery_offline.py']['content'] = (
                    '"""Check exact sealed scene and package identity offline."""\n'
                    'import json\n'
                    'from pathlib import Path\n'
                    'import unittest\n'
                    'from parking_runner import check_materialized_package\n'
                    'class ReviewedBundle(unittest.TestCase):\n'
                    '    def test_exact_reviewed_scene(self):\n'
                    '        expected = json.loads(Path("scene.json").read_text())\n'
                    '        check_materialized_package(Path.cwd(), expected)\n'
                    '        self.assertEqual(expected["source_packet_sha256"], '
                    'json.loads(Path("config.json").read_text())'
                    '["reviewed_source_packet"]["sha256"])\n'
                    '        self.assertFalse(expected["physical_realization_claimed"])\n')
                package['files'] = list(files.values()) + [
                    {'path': path, 'content': content}
                    for path, content in source_files[activity].items()]
                package['source_kind'] = 'retained_reviewed_native_site_packet'
                destination = staged / suffix / (candidate_id + '.json')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(package, indent=2) + '\n')
                variants.append({'id': candidate_id,
                                 'construction': destination.relative_to(staged).as_posix(),
                                 'construction_sha256': sha(destination),
                                 'source_packet_sha256': binding['packet_sha256'][activity],
                                 'preparation_status': 'review_and_cpu_proofs_pending'})
            entries.append({'case_id': case_id, 'activity': activity,
                            'variants': variants})
            runtime_entry = {key: value for key, value in template.items()
                             if key not in ('offline', 'compatibility', 'negative',
                                            'physical_preparation', 'post_capture',
                                            'delivery_acceptance', 'acquisition',
                                            'native_handoff', 'candidates')}
            runtime_entry['construction'] = variants[0]['construction']
            runtime_entry['construction_sha256'] = variants[0]['construction_sha256']
            runtime_entry['candidates'] = [{
                key: value for key, value in template['candidates'][0].items()
                if key not in ('offline', 'compatibility')
            }]
            runtime_entry['candidates'][0]['construction'] = variants[1]['construction']
            runtime_entry['candidates'][0]['construction_sha256'] = variants[1]['construction_sha256']
            runtime_entry['preparation_status'] = 'review_and_cpu_proofs_pending'
            runtime_entries.append(runtime_entry)
        manifest = {'format': 'parking-reviewed-rebound-execution-v1',
                    'assignment_id': ROOT.name,
                    'native_map': binding['native_map'],
                    'packet_sha256': binding['packet_sha256'],
                    'cases': entries,
                    'preparation_status': 'review_and_cpu_proofs_pending',
                    'physical_realization_claimed': False,
                    'legal_judgment': 'unresolved'}
        (staged / 'rebound-manifest.json').write_text(
            json.dumps(manifest, indent=2) + '\n')
        runtime_manifest = {**original, 'cases': runtime_entries,
                            'preparation_status': 'review_and_cpu_proofs_pending'}
        (staged / 'execution-manifest.json').write_text(
            json.dumps(runtime_manifest, indent=2) + '\n')
        staged.rename(output)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return output / 'rebound-manifest.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--park-packet', required=True)
    parser.add_argument('--stand-packet', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(rebind(args.park_packet, args.stand_packet, args.output_dir))


if __name__ == '__main__':
    main()
