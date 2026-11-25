"""Construct a source-bound 30-second unselected motorcycle witness pair."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
AID = HERE.name
OUT = HERE / 'extended-primary'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def main():
    assignment = (ROOT / 'inputs' / AID / 'assignment.json').read_bytes()
    plan = json.loads((HERE / 'case-plan.json').read_text())
    frozen = json.loads(assignment)
    assert frozen['assignment_id'] == AID
    assert plan['source_law']['text'] == 'No motorcycle or motor scooter shall be ridden upon any sidewalk of the City.'
    assert plan['source_law']['sha256'] == frozen['local_snapshot']['law_sha256']
    road = (NATIVE / 'road.xodr').read_bytes()
    lanes = {int(lane.attrib['id']): lane.attrib['type'] for lane in ET.fromstring(road).findall('.//lane')}
    assert lanes[1] == lanes[-1] == 'driving' and lanes[-2] == 'sidewalk'
    runner = (NATIVE / 'runner.py').read_text()
    assert runner.count('480') == 4 and runner.count("duration_s'] != 24") == 1
    runner = runner.replace('480', '600').replace("duration_s'] != 24", "duration_s'] != 30")
    runner = runner.replace('runtime/pipeline/scenario_pipeline', 'runtime/scenario_pipeline')
    runner = runner.replace('runtime/pipeline/python', 'runtime/python')
    saved_meter = (NATIVE / 'measure_saved.py').read_text().replace('480', '600')
    context_meter = (NATIVE / 'measure_context.py').read_text().replace('480', '600')
    finalizer = (NATIVE / 'finalize.py').read_text().replace('480', '600')
    context_preparer = (NATIVE / 'prepare_city_context.py').read_text()
    source_recording = json.loads((HERE / 'draft-candidates/witness_1/primary/construction.json').read_text())['recording_description']
    source_recording = json.loads(json.dumps(source_recording).replace('24 s', '30 s'))
    test = '''import json\nfrom pathlib import Path\nimport unittest\nfrom runner import check\n\nclass Construction(unittest.TestCase):\n    def test_exact(self):\n        c = json.loads(Path('config.json').read_text())\n        r = check(Path('.'), c['case_suffix'], c['candidate_id'])\n        self.assertEqual(r['track_rows'], 600)\n        self.assertFalse(r['original_native_observed'])\n    def test_swapped_witness_rejected(self):\n        c = json.loads(Path('config.json').read_text())\n        wrong = 'witness_2' if c['case_suffix'] == 'witness_1' else 'witness_1'\n        with self.assertRaises(ValueError):\n            check(Path('.'), wrong, c['candidate_id'])\n\nif __name__ == '__main__':\n    unittest.main()\n'''
    entries = []
    for suffix in ('witness_1', 'witness_2'):
      entry = None
      for candidate in ('primary', 'fallback1', 'fallback3'):
        source = NATIVE / 'drafts' / suffix / candidate
        config = json.loads((source / 'config.json').read_text())
        config['duration_s'] = 30
        config['assignment_sha256'] = sha(assignment)
        config['case_plan_sha256'] = sha((HERE / 'case-plan.json').read_bytes())
        rows = []
        for frame in range(600):
            x = round(10 + 4 * frame / 20, 4)
            if suffix == 'witness_1':
                y = -1.75
            else:
                fraction = max(0, min(1, (frame - config['policy']['lateral_start_frame']) /
                                       config['policy']['lateral_duration_frames']))
                y = round(-1.75 - 2.75 * fraction, 4)
            rows.append({'frame': frame, 'time_s': round(frame / 20, 4),
                         'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                         'requested_center_xy_m': [x, y], 'requested_speed_mps': 4.0,
                         'requested_body_width_m': .8,
                         'source_kind': 'authored_native_request'})
        tracks = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
        config['tracks_sha256'] = sha(tracks)
        config['road_sha256'] = sha(road)
        config['status'] = 'unselected_native_request_30s'
        overlap = [r['frame'] for r in rows if r['requested_center_xy_m'][1] - .4 < -3.5
                   and r['requested_center_xy_m'][1] + .4 > -5.5]
        expected_overlap = 0 if suffix == 'witness_1' else 600 - max(
            0, config['policy']['lateral_start_frame'] + config['policy']['lateral_duration_frames'] // 2)
        assert len(overlap) == expected_overlap
        files = [
            {'path': 'runner.py', 'content': runner},
            {'path': 'measure_saved.py', 'content': saved_meter},
            {'path': 'measure_context.py', 'content': context_meter},
            {'path': 'prepare_city_context.py', 'content': context_preparer},
            {'path': 'finalize.py', 'content': finalizer},
            {'path': 'assignment-source.json', 'content': assignment.decode()},
            {'path': 'authored-road.xodr', 'content': road.decode()},
            {'path': 'requested-tracks.jsonl', 'content': tracks.decode()},
            {'path': 'config.json', 'content': encoded(config).decode()},
            {'path': 'tests/test_construction.py', 'content': test},
        ]
        construction = {
            'case_id': AID + '__' + suffix, 'cell_id': 'C422978',
            'law_id': 'LVMC-11-38-030', 'actor': 'motorcycle_or_moped_operator',
            'entrypoint': 'runner.py', 'files': files,
            'measurement_plan': {'status': 'original_saved_measurement_pending',
                                 'method': 'Native motorcycle body intersection with city sidewalk'},
            'recording_description': source_recording,
            'status': 'unselected_cpu_draft',
        }
        path = OUT / suffix / ('construction.json' if candidate == 'primary' else candidate + '/construction.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded(construction))
        ref = {'id': candidate, 'construction': str(path.relative_to(OUT)),
               'construction_sha256': sha(path.read_bytes()),
               'requested_overlap_frames': len(overlap)}
        if candidate == 'primary':
            entry = {'case_id': construction['case_id'], 'kind': 'draft_not_selected',
                     'candidate_risk': {'status': 'physical',
                                        'reason': 'Original Native lateral motorcycle motion and camera visibility unverified'},
                     'candidates': [], **ref}
        else:
            ref['trigger'] = ({'source': 'original native-observed.jsonl',
                               'metric': 'moving sidewalk overlap and transition timing',
                               'failure_condition': 'Requested lateral transition is not reached in the original window'}
                              if candidate == 'fallback1' else
                              {'source': 'original sidewalk.mkv and capture/evidence.jsonl',
                               'metric': 'whole motorcycle body visible in sidewalk camera',
                               'failure_condition': 'Subject body falls outside camera pixels'})
            ref['changed_knobs'] = (['lateral_start_frame'] if candidate == 'fallback1'
                                    else ['camera_fov_deg'])
            entry['candidates'].append(ref)
      entries.append(entry)
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256'],
                'source_law_sha256': plan['source_law']['sha256'],
                'assignment_sha256': sha(assignment), 'cases': entries,
                'original_native_observed': False, 'city_authority_reviewed': False,
                'driveway_rule_composition_reviewed': False}
    (OUT / 'manifest.json').write_bytes(encoded(manifest))
    print(json.dumps({'manifest_sha256': sha((OUT / 'manifest.json').read_bytes()),
                      'cases': [(e['case_id'], e['requested_overlap_frames']) for e in entries]}))


if __name__ == '__main__':
    main()
