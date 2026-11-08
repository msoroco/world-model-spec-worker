"""Positive and tamper-negative CPU proof for paragraph (c)(1) saved processing."""
import json
from pathlib import Path
import shutil
import tempfile

from saved import prepare, measure, sha
from route_fallbacks import route

HERE = Path(__file__).resolve().parent


def change_json(path, action, jsonl=False):
    if jsonl:
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        action(rows[0])
        path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    else:
        value = json.loads(path.read_text())
        action(value)
        path.write_text(json.dumps(value)+'\n')


def expect_reject(action):
    try:
        action()
    except (ValueError, KeyError, FileNotFoundError):
        return
    raise AssertionError('tampered source accepted')


def run():
    manifest = json.loads((HERE/'offline/manifest.json').read_text())
    proof = json.loads((HERE/'offline/saved-proof.json').read_text())
    if proof['copied_manifest_sha256'] != sha(HERE/'offline/manifest.json'):
        raise ValueError('copied manifest changed')
    positives = negatives = 0
    for entry, saved_entry in zip(manifest['entries'], proof['entries']):
        bundle = HERE/entry['bundle']
        witness, candidate = bundle.parent.name, bundle.name
        raw = HERE/'offline/raw-fixtures'/witness/candidate
        saved = HERE/'offline/saved-fixtures'/witness/candidate
        if sha(bundle/'saved.py') != sha(HERE/'saved.py') or \
           sha(bundle/'fixture_raw.py') != sha(HERE/'fixture_raw.py') or \
           sha(bundle/'route_fallbacks.py') != sha(HERE/'route_fallbacks.py'):
            raise ValueError('copied processor differs')
        if any(sha(raw/name) != digest for name, digest in saved_entry['raw_hashes'].items()) or \
           any(sha(saved/name) != digest for name, digest in saved_entry['saved_hashes'].items()):
            raise ValueError('fixture hashes differ')
        if measure(bundle, saved) != saved_entry['measurement']:
            raise ValueError('saved measurement differs')
        if route(bundle, saved) != saved_entry['routing']:
            raise ValueError('measured routing differs')
        positives += 1
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            changes = (
                ('video_frames.jsonl', lambda row: row.__setitem__('native_frame', -1), True),
                ('native-raw-actors.jsonl', lambda row: row['ego']['body_native_xyz_m'][0].__setitem__(1, 200), True),
                ('frame-review.jsonl', lambda row: row.__setitem__('review_provenance', 'human_frame_review'), True),
                ('native-map-readback.json', lambda row: row['driving_lane_readback']['-2'].__setitem__('lane_id', -1), False),
                ('native-capture-report.json', lambda row: row.__setitem__('config_sha256', '0'*64), False),
            )
            for n, (name, mutate, jsonl) in enumerate(changes):
                bad = temp/f'raw-{n}'
                shutil.copytree(raw, bad)
                change_json(bad/name, mutate, jsonl)
                expect_reject(lambda b=bad, j=n: prepare(bundle, b, temp/f'saved-{j}', True))
                negatives += 1
            bad_saved = temp/'bad-saved'
            shutil.copytree(saved, bad_saved)
            change_json(bad_saved/'native-observed.jsonl',
                        lambda row: row['ego']['center_native_xyz_m'].__setitem__(0, -100), True)
            expect_reject(lambda: measure(bundle, bad_saved))
            negatives += 1
            bad_receipt = temp/'bad-receipt'
            shutil.copytree(saved, bad_receipt)
            change_json(bad_receipt/'preparation-receipt.json',
                        lambda row: row.__setitem__('delivery_ready', True))
            expect_reject(lambda: route(bundle, bad_receipt))
            negatives += 1
    result = {'format': 'c146314-paragraph-c1-saved-compatibility-v1',
              'positive': positives, 'tamper_negative': negatives,
              'synthetic_cpu_only': True, 'delivery_ready': False}
    (HERE/'offline/saved-compatibility.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(run()))
