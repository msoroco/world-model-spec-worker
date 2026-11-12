"""Build three physically distinct exact fallbacks per selected C230259 case."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
SUFFIXES = ('baseline_right', 'baseline_left', 'passing_left', 'closure_left',
            'three_lane_left', 'one_way_left', 'narrow_left')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f'{label} fallback replacement is not unique')
    return text.replace(before, after, 1)


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    generated = []
    for suffix in SUFFIXES:
        case_id = PREFIX + suffix
        entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
        primary = json.loads((HERE / entry['construction']).read_text())
        files = {item['path']: item for item in primary['files']}
        runner = primary['entrypoint']
        if runner not in files or 'right_half_cameras.py' not in files:
            raise ValueError('Exact fallback source files absent: ' + case_id)
        candidates = []
        for index in (1, 2, 3):
            value = json.loads(json.dumps(primary))
            paths = {item['path']: item for item in value['files']}
            if index == 1:
                if suffix == 'passing_left':
                    paths[runner]['content'] = replace_once(
                        paths[runner]['content'], 'target_speed_mps=10.0',
                        'target_speed_mps=7.5', 'passing speed')
                else:
                    paths['right_half_route.py']['content'] = replace_once(
                        paths['right_half_route.py']['content'], 'target_speed_mps=5.0',
                        'target_speed_mps=3.5', 'route speed')
                trigger = {'source': 'original trace.jsonl and ego_road_frames.jsonl',
                           'metric': 'body lateral overshoot m',
                           'failure_condition': 'subject body reaches unplanned roadway half or edge'}
                changed = ['Reduce target speed to contain body lateral overshoot']
            elif index == 2:
                paths[runner]['content'] = paths[runner]['content'].replace(
                    'vehicle.tesla.model3', 'vehicle.audi.tt')
                if 'vehicle.audi.tt' not in paths[runner]['content']:
                    raise ValueError('Alternate Native motor-vehicle blueprint absent')
                trigger = {'source': 'Native actor spawn log', 'metric': 'subject spawn success',
                           'failure_condition': 'primary motor-vehicle blueprint cannot spawn on selected route'}
                changed = ['Use alternate motor-vehicle blueprint while retaining original body readback']
            else:
                paths['right_half_cameras.py']['content'] = replace_once(
                    paths['right_half_cameras.py']['content'],
                    '"overview": ((-8, 0, 8)', '"overview": ((-10, 0, 10)',
                    'overview camera mount')
                trigger = {'source': 'four original camera streams and source decode',
                           'metric': 'road/body/exception visibility',
                           'failure_condition': 'overview camera fails to show selected roadway and subject path'}
                changed = ['Raise and move overview camera mount while retaining resolution, FOV and FFV1 source']
            value['mechanisms']['fallback_strategy'] = changed[0]
            value['mechanisms']['construction_status'] = 'exact_fallback_cpu_proof_pending'
            value['static_checks'].append('Fallback changes only the stated physical construction knob')
            path = HERE / f'construction-{suffix}-fallback{index}.json'
            write(path, value)
            candidates.append({'id': f'fallback{index}', 'construction': path.name,
                               'construction_sha256': sha(path), 'trigger': trigger,
                               'changed_knobs': changed})
            generated.append(str(path.name))
        entry['candidates'] = candidates
    write(manifest_path, manifest)
    return {'fallback_constructions': len(generated), 'manifest_sha256': sha(manifest_path)}


if __name__ == '__main__':
    print(json.dumps(build()))
