"""Independent row and speed contrast audit for the retained response factorial."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ACTORS = ('oncoming', 'overtaken')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof_path = HERE/'response-comparison-proof.json'
    proof = json.loads(proof_path.read_text())
    paths = {'none': HERE/'saved-fixtures'/'170',
             'oncoming': HERE/'response-fixtures'/'only-oncoming-170',
             'overtaken': HERE/'response-fixtures'/'only-overtaken-170',
             'both': HERE/'response-fixtures'/'reaction-170'}
    if (proof['format'] != 'c102951-controlled-response-factorial-v1' or
            proof['assignment_id'] != HERE.parent.name or
            proof['processor_sha256'] != sha(HERE/'measure_response.py') or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['delivery_ready'] or proof['causal_judgment'] is not None or
            proof['interference_judgment'] is not None or
            [row['mutation'] for row in proof['negatives']] !=
            ['ego_trajectory', 'sightline', 'unrequested_actor', 'road_readback'] or
            not all(row['rejected'] is True for row in proof['negatives'])):
        raise ValueError('Response factorial provenance, scope or status differs')
    sources = {name: {file: sha(folder/file) for file in ('native-observed.jsonl', 'road-readback.json')}
               for name, folder in paths.items()}
    if sources != proof['sources'] or len({item['road-readback.json'] for item in sources.values()}) != 1:
        raise ValueError('Response factorial source or road differs')
    groups = {name: load(folder/'native-observed.jsonl') for name, folder in paths.items()}
    if any(len(data) != 480 for data in groups.values()):
        raise ValueError('Response factorial saved row count differs')
    excluded = {actor+'_'+suffix for actor in ACTORS for suffix in ('speed_mps', 'x_m')}
    for i in range(480):
        base, both = groups['none'][i], groups['both'][i]
        if base['frame'] != i or abs(base['time_s']-(i+1)/20) > 1e-6:
            raise ValueError('Response factorial time/frame identity differs')
        for name, data in groups.items():
            row = data[i]
            if row.keys() != base.keys() or any(row[key] != base[key] for key in base.keys()-excluded):
                raise ValueError('Response factorial fixed saved fields differ')
            for actor in ACTORS:
                expected = both if name == 'both' or name == actor else base
                if any(row[actor+'_'+suffix] != expected[actor+'_'+suffix]
                       for suffix in ('speed_mps', 'x_m')):
                    raise ValueError('Response factorial changed the wrong actor')
    start, finish = proof['pass_window']
    if [start, finish] != [35, 134]:
        raise ValueError('Response factorial pass event window differs')
    drops = {}
    for name, group in groups.items():
        drops[name] = {}
        for actor in ACTORS:
            speeds = [row[actor+'_speed_mps'] for row in group]
            before = sorted(speeds[:20]); baseline = (before[9]+before[10])/2
            drops[name][actor] = round(max(0, baseline-min(speeds[start:finish+1])), 3)
            if name == actor or name == 'both':
                direction = -1 if actor == 'oncoming' else 1
                positions = [row[actor+'_x_m'] for row in group]
                if any(abs(positions[i]-positions[i-1]-direction*speeds[i]/20) > 1.1e-4
                       for i in range(1, len(group))):
                    raise ValueError('Response factorial speed-position continuity differs')
    if drops != proof['speed_drop_mps'] or drops != {
            'none': {'oncoming': 0, 'overtaken': 0},
            'oncoming': {'oncoming': 4, 'overtaken': 0},
            'overtaken': {'oncoming': 0, 'overtaken': 4},
            'both': {'oncoming': 4, 'overtaken': 4}}:
        raise ValueError('Independent response factorial metric differs')
    # Replay each control through the proof's deterministic row comparison.
    from prove_response_comparison import compare
    replayed = []
    for mutation in ('ego_trajectory', 'sightline', 'unrequested_actor', 'road_readback'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            copy = Path(temporary)/'changed'
            shutil.copytree(paths['oncoming'], copy)
            if mutation == 'road_readback':
                road = copy/'road-readback.json'; road.write_bytes(road.read_bytes()+b' ')
            else:
                changed = load(copy/'native-observed.jsonl')
                if mutation == 'ego_trajectory': changed[60]['ego_x_m'] += 1
                elif mutation == 'sightline': changed[60]['sightline_visible'] = False
                else: changed[60]['overtaken_speed_mps'] += 1
                (copy/'native-observed.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in changed))
            try:
                compare(dict(paths, oncoming=copy))
            except ValueError:
                replayed.append(mutation)
            else:
                raise ValueError('Independent response control accepted '+mutation)
    receipt = {'format': 'c102951-independent-response-factorial-audit-v1',
               'proof_sha256': sha(proof_path), 'saved_rows_checked': 1920,
               'negative_controls_replayed': replayed,
               'original_native_observed': False, 'accepted_comparison': False,
               'delivery_ready': False}
    (HERE/'response-comparison-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
