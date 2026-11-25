"""Build two exact parking cases and surveyed spawn fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'native/selected_primary'
AID = HERE.name


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    cfg0 = json.loads((BASE / 'config.json').read_text())
    src = (BASE / 'runner.py').read_text()
    test = (BASE / 'tests/test_bundle.py').read_text()
    manifest = {'assignment_id': AID, 'cases': []}
    for suffix, primary_spawn, alternate_spawn in (
        ('probe_01', 'device_spawn_xyz_m', 'fallback_device_spawn_xyz_m'),
        ('probe_02', 'obstructing_device_spawn_xyz_m', 'fallback_obstructing_device_spawn_xyz_m'),
    ):
        cid = AID + '__' + suffix
        entry = {'case_id': cid, 'candidate_risk': {'status': 'physical',
            'reason': 'Reviewed rack, device and pedestrian-corridor placement may reject surveyed Native spawn'},
            'candidates': []}
        for candidate, spawn in (('primary', primary_spawn), ('fallback1', alternate_spawn)):
            cfg = dict(cfg0)
            cfg.update(case_id=cid, selected_case_id=cid, candidate_id=candidate, spawn_key=spawn)
            runner = src.replace("CASE = AID + '__probe_01'", "CASE = AID + '__" + suffix + "'")
            runner = runner.replace("cfg.get('candidate_id') != 'primary'", "cfg.get('candidate_id') != '" + candidate + "'")
            files = [{'path': 'runner.py', 'content': runner},
                {'path': 'config.json', 'content': json.dumps(cfg, indent=2, sort_keys=True) + '\n'},
                {'path': 'tests/test_bundle.py', 'content': test},
                {'path': 'finalize_parking.py', 'content': (HERE / 'finalize_parking.py').read_text()},
                {'path': 'measure_parking.py', 'content': (HERE / 'native/measure_parking.py').read_text()}]
            construction = {'format': 'worker-construction', 'assignment_id': AID,
                'case_id': cid, 'cell_id': 'C229388', 'law_id': 'LVMC-11-40-170',
                'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                'recording_description': cfg['recording_description'],
                'measurement_plan': {'entrypoint': 'finalize_parking.py',
                    'source_files': ['video_frames.jsonl', 'native_parking_trace.jsonl', 'parking_context.json'],
                    'legal_result': None},
                'static_checks': ['exact selected case and four-camera capture contract',
                    'surveyed rack and placement sources', 'saved-source negative proof'],
                'termination_rules': ['600 original Native frames at 20 Hz',
                    'nonzero capture or restoration error retained'],
                'mechanisms': ['survey-gated cycle or scooter and attached operator',
                    'surveyed supporting rack and pedestrian corridor', 'four original FFV1 cameras',
                    'saved-only parking source finalizer'],
                'files': files}
            path = HERE / ('selected-primary-construction.json' if suffix == 'probe_01' and candidate == 'primary'
                else 'cases' / Path(suffix) / ('fallback1-construction.json' if candidate == 'fallback1'
                    else 'selected-primary-construction.json'))
            write(path, construction)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if candidate == 'primary':
                entry.update(construction=str(path.relative_to(HERE)), construction_sha256=digest)
                if suffix == 'probe_01':
                    (HERE / 'runner.py').write_text(runner)
                    write(HERE / 'config.json', cfg)
                    write(HERE / 'construction.json', construction)
                    (HERE / 'tests').mkdir(exist_ok=True)
                    (HERE / 'tests/test_bundle.py').write_text(test)
                    (HERE / 'measure_parking.py').write_text((HERE / 'native/measure_parking.py').read_text())
            else:
                entry['candidates'].append({'id': 'fallback1',
                    'construction': str(path.relative_to(HERE)), 'construction_sha256': digest,
                    'trigger': {'source': 'original Native spawn receipt', 'metric': 'device_spawn_failed',
                        'failure_condition': 'surveyed primary device spawn returns no actor'},
                    'changed_knobs': ['surveyed alternate device spawn at the same placement category']})
        manifest['cases'].append(entry)
    write(HERE / 'selected-offline-manifest.json', manifest)
    print(json.dumps({'cases': [row['case_id'] for row in manifest['cases']]}, sort_keys=True))


if __name__ == '__main__':
    main()
