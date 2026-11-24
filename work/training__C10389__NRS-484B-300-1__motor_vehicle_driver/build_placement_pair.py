"""Construct a controlled source-document availability pair for placement review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'cases/branch-requests'
SOURCE = BASE / 'officer_no_direction_stop'
SUFFIXES = {'placement_record_absent': False, 'placement_record_supplied': True}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    runner = (SOURCE / 'runner.py').read_text().replace('from officer_check import check', 'from placement_check import check')
    runner = runner.replace('    owned, encoders, logs, queues = [], {}, {}, {}',
                            "    write_new(output / 'placement-source-readback.json', checked['placement_source'])\n    owned, encoders, logs, queues = [], {}, {}, {}")
    if "placement-source-readback.json" not in runner:
        raise ValueError('Placement source readback was not inserted')
    check = (HERE / 'placement_check.py').read_text()
    finalizer = (HERE / 'branch-diagnostic-finalize.py').read_text()
    test = '''"""Exact placement source preflight."""\nimport json\nfrom pathlib import Path\nimport unittest\nfrom placement_check import check\nHERE=Path(__file__).resolve().parents[1]\nclass ExactPlacement(unittest.TestCase):\n def test_source(self):\n  result=check(HERE)\n  self.assertEqual(result['frames'],600)\n  self.assertIs(result['official_placement_verified'],False)\n  self.assertIs(result['original_native_observed'],False)\nif __name__=='__main__':unittest.main()\n'''
    outputs = []
    for suffix, present in SUFFIXES.items():
        for candidate in ('primary', 'fallback1'):
            src = SOURCE if candidate == 'primary' else BASE / 'officer_no_direction_stop-fallback1'
            target = BASE / (suffix if candidate == 'primary' else suffix + '-fallback1')
            target.mkdir(parents=True, exist_ok=True)
            for name in ('assignment-source.json', 'alley-stop.xodr', 'requested-tracks.jsonl'):
                (target / name).write_bytes((src / name).read_bytes())
            (target / 'runner.py').write_text(runner)
            (target / 'placement_check.py').write_text(check)
            (target / 'finalize.py').write_text(finalizer)
            (target / 'tests').mkdir(exist_ok=True)
            (target / 'tests/test_exact.py').write_text(test)
            record = {'format': 'c10389-placement-source-context-v1',
                      'source_kind': 'authored_cpu_context', 'document_present': present,
                      'document_type': 'authored_simulation_device_schedule' if present else None,
                      'document_issuer': 'scenario_worker' if present else None,
                      'device_id': '3891', 'road_id': 389, 'lane_id': -1,
                      'administrative_authenticity_verified': False,
                      'official_placement_verified': False, 'legal_verdict': None}
            write(target / 'placement-record.json', record)
            cfg = json.loads((src / 'config.json').read_text())
            cfg['case_id'] = HERE.name + '__' + suffix
            cfg['candidate_id'] = candidate
            cfg['placement_record_sha256'] = sha(target / 'placement-record.json')
            cfg['placement_document_present'] = present
            cfg['selected_case_id'] = cfg['case_id']
            cfg['case']['case_id'] = cfg['case_id']
            cfg['recording_description']['context_inputs'].append({
                'name': 'placement_provenance_record', 'unit': 'source_document',
                'method': 'Hash-checked authored device schedule availability; authority unverified'})
            cfg['case']['recording_description'] = cfg['recording_description']
            cfg['status'] = 'authored_unselected_placement_request'
            write(target / 'config.json', cfg)
            names = ('runner.py', 'placement_check.py', 'config.json', 'assignment-source.json',
                     'alley-stop.xodr', 'requested-tracks.jsonl', 'placement-record.json',
                     'finalize.py', 'tests/test_exact.py')
            construction = {'entrypoint': 'runner.py', 'case_id': cfg['case_id'],
                            'law_id': cfg['law_id'], 'cell_id': cfg['cell_id'], 'actor': cfg['actor'],
                            'files': [{'path': name, 'content': (target / name).read_text()} for name in names],
                            'recording_description': cfg['recording_description'],
                            'status': 'unselected_cpu_construction'}
            write(target / 'construction.json', construction)
            outputs.append({'case_id': cfg['case_id'], 'candidate_id': candidate,
                            'construction_sha256': sha(target / 'construction.json'),
                            'placement_record_sha256': cfg['placement_record_sha256'],
                            'document_present': present, 'official_placement_verified': False})
    return outputs


if __name__ == '__main__':
    print(json.dumps(build()))
