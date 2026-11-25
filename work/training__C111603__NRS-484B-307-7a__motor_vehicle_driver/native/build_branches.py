"""Materialize selected pedestrian and concurrent-indication Native bundles."""
import copy
import hashlib
import json
from pathlib import Path

from branch_scenarios import BRANCHES, rows

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def channel(name):
    return {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': '600 source-joined original Native actor and signal-request rows',
            'time_window': '600 frames / 30 seconds',
            'reference_frame': 'original world and frame time',
            'uncertainty': 'Physical signal governance, lawful pedestrian status and cautiousness require review'}


def build():
    base = json.loads((ROOT / 'native/selected-controlled_1-primary-construction.json').read_text())
    template_config = json.loads(next(item['content'] for item in base['files']
                                      if item['path'] == 'config.json'))
    runner = (ROOT / 'native/native_runner_branches.py').read_text()
    finalizer = (ROOT / 'native/finalize_branches.py').read_text()
    branch_source = (ROOT / 'native/branch_scenarios.py').read_text()
    branch_keys = tuple(BRANCHES)
    output = []
    for branch, spec in BRANCHES.items():
        request = rows(branch)
        request_sha = hashlib.sha256((''.join(json.dumps(row, sort_keys=True) + '\n'
                                          for row in request)).encode()).hexdigest()
        for candidate in ('primary', 'fallback1'):
            construction = copy.deepcopy(base)
            case = AID + '__' + branch
            construction['case_id'] = case
            construction['status'] = 'selected_delivery_prepared'
            construction['recording_description'] = {
                'channels': [channel(name) for name in
                             ('ego_motion', 'pedestrian_motion', 'arrow_request',
                              'concurrent_request')],
                'context_inputs': [],
                'limitations': ['Request is not official signal governance or legal status.',
                                'Original pixels, lawful pedestrian status and cautiousness require review.']}
            construction['measurement_plan'] = ('Join 600 saved actor and signal-request rows to four camera sources; '
                                                'measure timing while retaining legal status unknown.')
            construction['mechanisms'] = ['30-second synchronous Native capture',
                                          'four original full-profile camera sources',
                                          'pedestrian or concurrent signal-request intervention',
                                          'source-bound saved-only measurement']
            config = copy.deepcopy(template_config)
            config.update(case_id=case, selected_case_id=case,
                          supported_case_ids=[AID + '__' + key for key in branch_keys],
                          candidate_id=candidate,
                          case_suffix=branch,
                          ego_release_frame=spec['release_frame'],
                          requested_movement=spec['movement'],
                          requested_concurrent_straight_indication=spec['concurrent_straight'],
                          branch_request_sha256=request_sha,
                          ego_throttle=0.22 if candidate == 'primary' else 0.28,
                          pedestrian_lawful_status=None,
                          other_traffic_lawful_status=None,
                          cautiousness_legal_judgment=None,
                          recording_description=construction['recording_description'])
            config['case']['case_id'] = case
            contents = {'config.json': json.dumps(config, indent=2) + '\n',
                        'runner.py': runner, 'finalize.py': finalizer,
                        'branch_scenarios.py': branch_source}
            seen = set()
            for item in construction['files']:
                if item['path'] in contents:
                    item['content'] = contents[item['path']]
                    seen.add(item['path'])
            for path, content in contents.items():
                if path not in seen:
                    construction['files'].append({'path': path, 'content': content})
            target = ROOT / f'native/selected-{branch}-{candidate}-construction.json'
            dump(target, construction)
            output.append({'case': branch, 'candidate': candidate,
                           'construction': str(target.relative_to(ROOT)), 'sha256': sha(target)})
    dump(ROOT / 'native/selected-branch-constructions.json', output)
    return output


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
