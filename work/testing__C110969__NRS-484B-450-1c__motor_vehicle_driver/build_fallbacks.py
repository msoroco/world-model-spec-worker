"""Build source-gated engineering alternatives for measured physical failures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    draft = json.loads((HERE/'execution-manifest.draft.json').read_text())
    rows = []
    for entry in draft['cases']:
        row = dict(entry)
        if entry['candidate_risk']['status'] == 'physical':
            primary = json.loads((HERE/entry['construction']).read_text())
            fallback = json.loads(json.dumps(primary))
            config_entry = next(item for item in fallback['files']
                                if item['path'] == 'config.json')
            config = json.loads(config_entry['content'])
            through = entry['case_id'].endswith('__through_motion')
            if through:
                config['controller_profile'] = {
                    'brake_distance_m': 2.0, 'throttle_gain': 0.28,
                    'through_speed_floor_mps': 3.0}
                changed = ['controller_profile.throttle_gain: 0.2 to 0.28',
                           'controller_profile.through_speed_floor_mps: 2.0 to 3.0']
                trigger = {'source': 'source-sealed original trace.jsonl and reviewed intersection boundary',
                           'metric': 'final body footprint clearance and longitudinal progress',
                           'failure_condition': 'body not wholly beyond reviewed far-side boundary by final frame'}
            else:
                config['controller_profile'] = {
                    'brake_distance_m': 3.5, 'throttle_gain': 0.2,
                    'through_speed_floor_mps': 2.0}
                changed = ['controller_profile.brake_distance_m: 2.0 to 3.5']
                trigger = {'source': 'source-sealed original trace.jsonl and reviewed intersection boundary',
                           'metric': 'final body footprint and measured speed relative to reviewed inside destination',
                           'failure_condition': 'body passed the reviewed destination before stable requested halt'}
            config_entry['content'] = json.dumps(config, indent=2)+'\n'
            suffix = entry['case_id'].removeprefix(HERE.name+'__')
            path = HERE/('construction-'+suffix+'-fallback1.json')
            path.write_text(json.dumps(fallback, indent=2)+'\n')
            row['candidates'] = [{'id': 'fallback1', 'construction': path.name,
                                  'construction_sha256': sha(path),
                                  'trigger': trigger, 'changed_knobs': changed}]
        rows.append(row)
    provisional = {'format': 'worker-execution-manifest',
                   'assignment_id': HERE.name,
                   'status': 'fallback_offline_pending_source_review',
                   'cases': rows}
    (HERE/'execution-manifest.fallback-offline.json').write_text(
        json.dumps(provisional, sort_keys=True, indent=2)+'\n')
    print('built', sum(bool(row.get('candidates')) for row in rows),
          'exact bounded fallback constructions')


if __name__ == '__main__':
    build()
