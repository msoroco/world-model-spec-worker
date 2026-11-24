"""Split existing synthetic request into independently hashed saved sources."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from saved_finalizer import finalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def reject(folder, hashes, case, expected):
    try:
        finalize(folder, hashes, case)
    except ValueError as error:
        if expected not in str(error):
            raise RuntimeError('unexpected rejection: ' + str(error))
        return str(error)
    raise RuntimeError('invalid saved source passed: ' + expected)


def main():
    scratch = Path(os.environ['TMPDIR']) / 'c109166-287-1e-saved'
    scratch.mkdir(parents=True, exist_ok=True)
    context = HERE / 'diagnostic-diagonal' / 'context.json'
    positives = []
    negatives = {}
    for case in ('controlled_1', 'controlled_2'):
        folder = scratch / case
        folder.mkdir(exist_ok=True)
        rows = [json.loads(line) for line in
                (HERE / 'diagnostic-diagonal' / (case + '.jsonl')).read_text().splitlines()]
        people = [{key: row[key] for key in
                   ('frame', 'time_s', 'pedestrian_xy_m', 'footprint_xy_m', 'source_kind')}
                  for row in rows]
        devices = [{key: row[key] for key in
                    ('frame', 'time_s', 'device_id', 'device_state',
                     'diagonal_movement_governed', 'source_kind')}
                   for row in rows]
        write_rows(folder / 'pedestrian.jsonl', people)
        write_rows(folder / 'device.jsonl', devices)
        (folder / 'context.json').write_bytes(context.read_bytes())
        hashes = {name: sha(folder / name) for name in
                  ('pedestrian.jsonl', 'device.jsonl', 'context.json')}
        result = finalize(folder, hashes, case)
        if (result['physical_crossing_observed'] or result['legal_verdict'] is not None or
                result['requested_first_entry_frame'] != 100):
            raise RuntimeError('saved diagnostic overstated result')
        positives.append(result)
        if case == 'controlled_2':
            negatives['missing_device'] = reject(folder, {k: v for k, v in hashes.items()
                                                          if k != 'device.jsonl'}, case,
                                                  'all saved source hashes required')
            negatives['stale_device_hash'] = reject(
                folder, {**hashes, 'device.jsonl': '0' * 64}, case, 'hash mismatch')
            altered = copy.deepcopy(devices)
            altered[100]['time_s'] = -1
            write_rows(folder / 'device.jsonl', altered)
            negatives['bad_time_join'] = reject(
                folder, {**hashes, 'device.jsonl': sha(folder / 'device.jsonl')},
                case, 'frame/time join')
            altered = copy.deepcopy(devices)
            altered[100]['device_id'] = 'other'
            write_rows(folder / 'device.jsonl', altered)
            negatives['wrong_device'] = reject(
                folder, {**hashes, 'device.jsonl': sha(folder / 'device.jsonl')},
                case, 'governing diagonal device')
            altered = copy.deepcopy(devices)
            altered[100]['device_state'] = 'diagonal_walk'
            write_rows(folder / 'device.jsonl', altered)
            negatives['wrong_first_entry'] = reject(
                folder, {**hashes, 'device.jsonl': sha(folder / 'device.jsonl')},
                case, 'first-entry requested instruction')
            write_rows(folder / 'device.jsonl', devices)
            altered_people = copy.deepcopy(people)
            altered_people[200]['footprint_xy_m'] = []
            write_rows(folder / 'pedestrian.jsonl', altered_people)
            negatives['missing_full_body'] = reject(
                folder, {**hashes, 'pedestrian.jsonl': sha(folder / 'pedestrian.jsonl')},
                case, 'full-body source')
            write_rows(folder / 'pedestrian.jsonl', people)
            bad_context = json.loads(context.read_text())
            bad_context['official_device_original_review'] = 'verified'
            (folder / 'context.json').write_text(json.dumps(bad_context) + '\n')
            negatives['unsupported_authority'] = reject(
                folder, {**hashes, 'context.json': sha(folder / 'context.json')},
                case, 'authority/context')
            (folder / 'context.json').write_bytes(context.read_bytes())
    if [p['requested_first_entry_state'] for p in positives] != [
            'diagonal_walk', 'diagonal_dont_walk']:
        raise RuntimeError('controlled first-entry pair differs')
    proof = {'format': 'c109166-287-1e-saved-finalizer-proof-v1',
             'source_kind': 'synthetic_scene_request', 'positive': positives,
             'rejected_negatives': negatives, 'saved_finalizer_sha256': sha(
                 HERE / 'native' / 'saved_finalizer.py'),
             'selected': False, 'physical_crossing_observed': False,
             'official_device_verified': False, 'legal_verdict_claimed': False}
    output = HERE / 'saved-finalizer-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive': len(positives), 'rejected_negatives': len(negatives),
                      'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
