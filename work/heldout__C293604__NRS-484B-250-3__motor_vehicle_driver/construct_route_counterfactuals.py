"""Build four synthetic original-shaped route-category sources and prove exclusions."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work/heldout__C293604__NRS-484B-250-3__motor_vehicle_driver'
OUT = ROOT / '.runtime-work/c293604-linked-review/route-counterfactuals'
sys.path.insert(0, str(WORK))
from opposing_left_measurement import measure_opposing_left


def digest(path): return sha256(Path(path).read_bytes()).hexdigest()


def build():
    source = json.loads((WORK / 'diagnostic-opposing-left.json').read_text())['files']
    required = ('opposing_left_context.json', 'opposing_left_participants.jsonl', 'video_frames.jsonl')
    if any(name not in source for name in required):
        raise ValueError('Exact diagnostic lacks original opposing-left sources')
    base = json.loads(source['opposing_left_context.json'])
    first = base['turning_route'][0]['heading_xy']
    scenarios = {
        'opposite_left': (True, True),
        'same_direction_left': (False, True),
        'opposite_straight': (True, False),
        'same_direction_straight': (False, False),
    }
    rows = []
    for name, (opposite, leftward) in scenarios.items():
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        context = deepcopy(base)
        if not opposite:
            context['opposite_route'][0]['heading_xy'] = first
        if not leftward:
            context['turning_route'][-1]['heading_xy'] = first
        (folder / 'opposing_left_context.json').write_text(json.dumps(context, indent=2) + '\n')
        for item in required[1:]:
            (folder / item).write_text(source[item])
        if opposite and leftward:
            result = measure_opposing_left(folder)['value']
            if not (result['approach_heading_dot'] <= -.8 and result['planned_left_cross'] >= .5):
                raise ValueError('Positive original route category was not constructed')
            status = 'measured_positive'
            values = {'approach_heading_dot': result['approach_heading_dot'],
                      'planned_left_cross': result['planned_left_cross']}
        else:
            try: measure_opposing_left(folder)
            except ValueError as error:
                if 'does not establish opposing leftward plan' not in str(error): raise
            else: raise ValueError('Nonqualifying route category passed original-source measurement')
            status = 'rejected_by_source_measurement'
            values = {}
        rows.append({'category': name, 'opposite': opposite, 'leftward': leftward,
                     'status': status, 'source_sha256': {item: digest(folder/item) for item in required},
                     'measured': values})
    if len({row['source_sha256']['opposing_left_context.json'] for row in rows}) != 4:
        raise ValueError('Four category sources must be distinct')
    receipt = {'format':'worker-opposing-left-route-counterfactuals',
               'source_spec_sha256': digest(WORK/'diagnostic-opposing-left.json'),
               'categories': rows, 'actual_native_route_claimed': False,
               'physical_or_legal_acceptance_claimed': False}
    path = Path(__file__).with_name('route-counterfactual-proof.json')
    path.write_text(json.dumps(receipt, indent=2)+'\n')
    return {'categories': len(rows), 'positive': 1, 'negative': 3, 'proof_sha256': digest(path)}

if __name__ == '__main__': print(json.dumps(build()))
