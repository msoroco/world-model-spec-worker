"""Exercise exact-case materialization/offline checks with synthetic site bytes.

All generated source and receipts stay under .runtime-work. They are never
reviewed roadway sources or production offline receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from case_protocol import ASSIGNMENT, SUFFIXES
from source_bindings import route_digest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_signal_crossing import MAP, REVIEW, packet


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    scratch = REPO / '.runtime-work' / 'c125751-diagnostic-runtime-3'
    if scratch.exists():
        raise ValueError('Retain prior diagnostic proof; remove only the named .runtime-work folder to rerun')
    scratch.mkdir(parents=True)
    site = packet()
    raw_packet = json.dumps(site, sort_keys=True).encode()
    source_files = {'map.xodr': MAP, 'review.json': REVIEW,
                    'source-packet.json': raw_packet}
    entries = []
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        construction = json.loads((ROOT / 'cases' / suffix / 'construction.json').read_text())
        for item in construction['files']:
            if item['path'] == 'case-spec.json':
                spec = json.loads(item['content'])
                spec.update(source_packet_sha256=sha(raw_packet), map_sha256=sha(MAP),
                            crossing_id=site['crossing_id'],
                            ego_route_sha256=route_digest(site['ego_route_xy_m']),
                            other_route_sha256=route_digest(site['other_route_xy_m']),
                            ego_blueprint='vehicle.cpu.fixture.ego',
                            other_blueprint='vehicle.cpu.fixture.other')
                item['content'] = json.dumps(spec, indent=2) + '\n'
        for name, body in source_files.items():
            construction['files'].append({'path': 'reviewed-sources/' + name,
                                          'source': 'synthetic_fixture',
                                          'content': body.decode()})
        construction['files'].append({
            'path': 'tests/test_offline.py', 'source': 'synthetic_fixture',
            'content': 'import json, unittest\nfrom pathlib import Path\n'
                       'class OfflineFixtureTest(unittest.TestCase):\n'
                       '    def test_source_gate(self):\n'
                       '        root = Path(__file__).resolve().parents[1]\n'
                       '        spec = json.loads((root / "case-spec.json").read_text())\n'
                       '        self.assertEqual(spec["source_status"], "original_review_required")\n'
                       '        self.assertTrue((root / "reviewed-sources/map.xodr").is_file())\n'})
        relative = 'cases/' + suffix + '/construction.json'
        path = scratch / relative
        save(path, construction)
        entries.append({'case_id': case_id, 'construction': relative,
                        'construction_sha256': sha(path.read_bytes())})
    save(scratch / 'execution-manifest.json', {'cases': entries,
                                                'diagnostic_fixture': True})
    proofs = []
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work' / 'c125751-proof')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        output = scratch / 'offline' / suffix
        output.parent.mkdir(exist_ok=True)
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'offline', '--manifest', str(scratch / 'execution-manifest.json'),
                   '--case', case_id, '--output', str(output)]
        completed = subprocess.run(command, cwd=REPO, env=env,
                                   capture_output=True, text=True)
        (scratch / ('offline-' + suffix + '.log')).write_text(
            completed.stdout + completed.stderr)
        proofs.append({'case_id': case_id, 'exit_code': completed.returncode,
                       'offline_log_sha256': sha((output / 'offline.log').read_bytes())
                       if (output / 'offline.log').is_file() else None,
                       'diagnostic_fixture': True})
    save(scratch / 'diagnostic-offline-proof.json', {'cases': proofs,
         'production_acceptance_claimed': False})
    print(json.dumps(proofs, indent=2))
    if any(item['exit_code'] != 0 for item in proofs):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
