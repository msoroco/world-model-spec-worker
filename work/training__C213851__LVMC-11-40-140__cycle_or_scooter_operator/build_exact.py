"""Materialize source-bound sidewalk crossing attempts and surveyed spawn fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE/'native'
AID = HERE.name


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    template = json.loads((BASE/'config.json').read_text())
    runner = (BASE/'runner.py').read_text()
    test = (BASE/'tests/test_runner.py').read_text()
    entries = []
    for suffix, mode in (('probe_01', 'stop_and_yield'), ('probe_02', 'roll_through')):
        cid = AID+'__'+suffix
        entry = {'case_id': cid, 'candidate_risk': {'status': 'physical',
            'reason': 'Surveyed bicycle spawn can be occupied or physically unsuitable at the driveway while preserving the same crossing path'},
            'candidates': []}
        for candidate, spawn in (('primary', 'rider_spawn_xyz_yaw_deg'),
                                  ('fallback1', 'fallback_rider_spawn_xyz_yaw_deg')):
            cfg = dict(template)
            cfg.update(case_id=cid, selected_case_id=cid, candidate_id=candidate,
                       control_mode=mode, spawn_key=spawn)
            files = [{'path': 'runner.py', 'content': runner},
                {'path': 'config.json', 'content': json.dumps(cfg, indent=2, sort_keys=True)+'\n'},
                {'path': 'tests/test_runner.py', 'content': test},
                {'path': 'finalize_sidewalk.py', 'content': (HERE/'finalize_sidewalk.py').read_text()},
                {'path': 'sidewalk_saved_measure.py', 'content': (HERE/'sidewalk_saved_measure.py').read_text()}]
            construction = {'format': 'worker-construction', 'assignment_id': AID,
                'case_id': cid, 'cell_id': 'C213851', 'law_id': 'LVMC-11-40-140',
                'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                'recording_description': cfg['recording_description'],
                'measurement_plan': {'entrypoint': 'finalize_sidewalk.py',
                    'source_files': ['video_frames.jsonl', 'sidewalk-native.jsonl', 'sidewalk_context.json'],
                    'legal_result': None},
                'static_checks': ['exact residence-driveway bicycle source plan',
                    'four original cameras and 600 synchronized frames',
                    'survey-gated sidewalk continuity and pedestrian conflict'],
                'termination_rules': ['600 original Native frames at 20 Hz',
                    'retain failed Native source attempt'],
                'mechanisms': ['survey-gated bicycle and pedestrian crossing',
                    'stop-and-yield versus roll-through controller comparison',
                    'source-reviewed sidewalk area, boundary and conflict',
                    'four original FFV1 cameras'], 'files': files}
            rel = ('selected-primary-construction.json' if suffix == 'probe_01' and candidate == 'primary'
                   else 'cases/'+suffix+'/'+candidate+'-construction.json')
            path = HERE/rel
            write(path, construction)
            if candidate == 'primary':
                entry.update(construction=rel, construction_sha256=sha(path))
                if suffix == 'probe_01':
                    (HERE/'runner.py').write_text(runner)
                    write(HERE/'config.json', cfg)
                    write(HERE/'construction.json', construction)
                    (HERE/'tests').mkdir(exist_ok=True)
                    (HERE/'tests/test_runner.py').write_text(test)
            else:
                entry['candidates'].append({'id': candidate, 'construction': rel,
                    'construction_sha256': sha(path),
                    'trigger': {'source': 'original Native spawn receipt',
                        'metric': 'rider_spawn_failed',
                        'failure_condition': 'surveyed primary bicycle spawn returns no actor'},
                    'changed_knobs': ['surveyed alternate bicycle spawn before same sidewalk boundary']})
        entries.append(entry)
    write(HERE/'selected-offline-manifest.json', {'assignment_id': AID, 'cases': entries})
    print(json.dumps({'cases': [e['case_id'] for e in entries]}, sort_keys=True))


if __name__ == '__main__':
    main()
