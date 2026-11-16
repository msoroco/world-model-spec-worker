"""Bind the eight selected diagnostic candidates to current CPU receipts.

This audit makes no original Native or legal safety claim.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
WITNESSES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = ('native-raw-actors.jsonl', 'video_frames.jsonl',
           'native-map-readback.json', 'capture/evidence.jsonl',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def check_one(witness, candidate, case, compatibility, receipt, result, construction, source_dir):
    case_id = f'{ROOT.name}__{witness}'
    expected_sha = case['construction_sha256'] if candidate == 'primary' else next(
        x['construction_sha256'] for x in case['candidates'] if x['id'] == candidate)
    require(construction['case_id'] == case_id and sha(source_dir/'construction.json') == expected_sha,
            'Selected construction or case changed')
    require(compatibility['case_id'] == receipt['case_id'] == result['case_id'] == case_id and
            compatibility['candidate_id'] == receipt['candidate_id'] == candidate,
            'Receipt case/candidate binding changed')
    require(compatibility['construction_sha256'] == expected_sha and compatibility['passed'] and
            compatibility['negative_removed'] and compatibility['negative_error_contains'],
            'Compatibility proof missing or stale')
    require(receipt['passed'] and receipt['recorded_only'] and receipt['originals_preserved'] and
            receipt['timestamp_joins']['passed'] and receipt['timestamp_joins']['frames'] == 240 and
            receipt['final_video_checks']['passed'] and receipt['final_video_checks']['frames'] == 240 and
            not receipt['missing_evidence'], 'Saved processing proof missing')
    require(result['provenance_kind'] == 'synthetic_local_diagnostic' and
            not result['accepted'] and not receipt['physical_acceptance_claimed'] and
            not receipt['legal_acceptance_claimed'], 'Diagnostic overclaims acceptance')
    hashes = receipt['original_source_hashes']
    require(all(s in hashes and (source_dir/s).is_file() and sha(source_dir/s) == hashes[s]
                for s in SOURCES), 'Original acquisition hash changed')
    require(result['physical_checks']['maneuver']['status'] == 'unverified' and
            result['measured_values']['measured_pass_body_clearance_m'] > 0,
            'Physical scope or gap changed')
    return {'witness': witness, 'candidate': candidate,
            'case_id': case_id, 'construction_sha256': expected_sha,
            'body_clearance_m': result['measured_values']['measured_pass_body_clearance_m'],
            'source_hashes': {s: hashes[s] for s in SOURCES}}


def reject_modified(args, label):
    try:
        check_one(*args)
    except (ValueError, KeyError):
        return label
    raise AssertionError('Tampered receipt accepted: ' + label)


def prove():
    manifest = read(ROOT/'execution-manifest-unified-draft.json')
    cases = {x['case_id'].rsplit('__', 1)[-1]: x for x in manifest['cases']}
    require(set(cases) == set(WITNESSES), 'Selected case pair missing')
    positives = []; negatives = []
    for witness in WITNESSES:
        for candidate in CANDIDATES:
            prefix = REPO/'.runtime-work'/f'c146314-210-2-{witness}-{candidate}'
            compatibility = read(Path(str(prefix)+'-compat-update060')/'compatibility.json')
            saved = Path(str(prefix)+'-fresh-update060-saved')/'v0001'
            receipt = read(saved/'processing.json')
            result = read(Path(receipt['result']))
            construction = read(ROOT/('selected-primary' if candidate == 'primary' else 'selected-fallbacks')/
                                witness/('construction.json' if candidate == 'primary' else candidate+'/construction.json'))
            attempt = Path(str(prefix)+'-fresh-update060-attempt')
            args = [witness, candidate, cases[witness], compatibility, receipt, result, construction, attempt]
            positives.append(check_one(*args))
            altered = copy.deepcopy(args); altered[4]['original_source_hashes']['native-raw-actors.jsonl'] = '0'*64
            negatives.append(reject_modified(altered, witness+'-'+candidate+'-changed-source'))
            altered = copy.deepcopy(args); altered[3]['negative_removed'] = False
            negatives.append(reject_modified(altered, witness+'-'+candidate+'-missing-negative-proof'))
            altered = copy.deepcopy(args); altered[5]['accepted'] = True
            negatives.append(reject_modified(altered, witness+'-'+candidate+'-false-acceptance'))
    for candidate in CANDIDATES:
        pair = [x for x in positives if x['candidate'] == candidate]
        require(len(pair) == 2 and pair[0]['body_clearance_m'] > pair[1]['body_clearance_m'],
                'Controlled measured clearance sweep absent')
    return {'format':'c146314-210-2-selected-cpu-matrix-v1', 'passed': True,
            'positive_diagnostic_candidates':positives, 'negative_rejections':negatives,
            'original_native_observed':False, 'physical_acceptance_claimed':False,
            'legal_safety_verdict':None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
