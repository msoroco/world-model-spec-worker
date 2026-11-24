"""Bind 56 fresh current-runtime short public receipts without selecting delivery."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SOURCE = WORK / 'current-runtime-refresh-short-draft-manifest.json'
INDEX = WORK / 'current-runtime-refresh-short-public-index.json'
TARGET = WORK / 'current-runtime-refresh-short-bound-manifest.json'
SHORT_ONLY = WORK / 'current-runtime-refresh-short-only-audit-manifest.json'
PORTABLE = WORK / 'current-runtime-refresh-short-public'
SCRATCH = REPO / '.runtime-work/owner150142/runtime-refresh-reference'
SHORTS = {'reference', 'contrast', 'ordinary_red_signed',
          'armored_car_signed_business', 'armored_car_signed_no_business',
          'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
          'emergency_vehicle_signed_business',
          'emergency_vehicle_signed_no_business',
          'emergency_vehicle_unsigned_business',
          'emergency_vehicle_unsigned_no_business',
          'mail_adjacent_deposit', 'mail_adjacent_no_deposit',
          'mail_no_box_deposit'}
VARIANTS = ('primary', 'fallback1', 'fallback2', 'fallback3')
CHECKS = {'selected_measurements', 'negative_case_source',
          'lean_decoder', 'final_decode'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                     dir=SCRATCH, delete=False) as stream:
        json.dump(obj, stream, sort_keys=True, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, path)


def copy_once(source, target):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=SCRATCH,
                                     delete=False) as stream:
        stream.write(source.read_bytes())
        temporary = Path(stream.name)
    os.replace(temporary, target)


def run():
    data = json.loads(SOURCE.read_text())
    index = json.loads(INDEX.read_text())
    if (index['completed'] != 52 or index['expected'] != 52 or
            index['source_manifest_sha256'] != sha(SOURCE)):
        raise ValueError('All 52 nonreference current-runtime receipts are required')
    current = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    if data['runtime_manifest_sha256'] != current:
        raise ValueError('Draft does not bind active runtime')
    for candidate in VARIANTS:
        src = SCRATCH / candidate
        dst = PORTABLE / 'reference' / candidate
        if not (src / 'compatibility.json').is_file():
            raise ValueError('Fresh current-runtime reference receipt missing: ' + candidate)
        dst.mkdir(parents=True, exist_ok=True)
        for old, new in (('compatibility.json', 'compatibility.json'),
                         ('compatibility-analysis.log', 'positive-analysis.log'),
                         ('negative-analysis.log', 'negative-analysis.log')):
            source, target = src / old, dst / new
            if target.exists() and sha(target) != sha(source):
                raise ValueError('Portable reference proof differs: ' + candidate)
            if not target.exists():
                copy_once(source, target)
    short_entries = []
    for entry in data['cases']:
        suffix = entry['case_id'].removeprefix(WORK.name + '__')
        if suffix not in SHORTS:
            continue
        short_entries.append(entry)
        fields = {'primary': entry,
                  **{item['id']: item for item in entry['candidates']}}
        if set(fields) != set(VARIANTS):
            raise ValueError('Short candidate inventory changed: ' + suffix)
        for candidate in VARIANTS:
            field = fields[candidate]
            directory = PORTABLE / suffix / candidate
            receipt = directory / 'compatibility.json'
            positive = directory / 'positive-analysis.log'
            negative = directory / 'negative-analysis.log'
            if not all(path.is_file() for path in (receipt, positive, negative)):
                raise ValueError('Incomplete current-runtime proof: ' + suffix + '/' + candidate)
            proof = json.loads(receipt.read_text())
            if (proof['case_id'] != entry['case_id'] or
                    proof['candidate_id'] != candidate or
                    proof['construction_sha256'] != field['construction_sha256'] or
                    proof['runtime_manifest_sha256'] != current or
                    proof['passed'] is not True or
                    not CHECKS <= set(proof['checks']) or
                    proof['log_sha256'] != sha(positive) or
                    proof['negative_log_sha256'] != sha(negative) or
                    proof['negative_error_contains'] not in negative.read_text()):
                raise ValueError('Fresh proof binding failed: ' + suffix + '/' + candidate)
            field['compatibility'] = {
                'receipt': str(receipt.relative_to(WORK)),
                'sha256': sha(receipt),
                'log': str(positive.relative_to(WORK)),
                'negative_log': str(negative.relative_to(WORK)),
            }
            field['negative'] = {'log': str(negative.relative_to(WORK))}
    if len(short_entries) != 14:
        raise ValueError('All 14 short cases must bind fresh proofs')
    data['status'] = 'draft_current_runtime_refresh_short_public_bound'
    data['delivery_ready'] = False
    store(TARGET, data)
    subset = dict(data)
    subset['cases'] = short_entries
    store(SHORT_ONLY, subset)
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('Export output root under .runtime-work before direct runtime import')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.package_compatibility import check_receipts
    from worker_exchange.candidate_constructions import validate
    check_receipts(REPO, WORK, subset)
    plan = json.loads((WORK / 'case-plan.json').read_text())
    for entry in short_entries:
        validate(WORK, entry, plan['law_id'], plan['cell_id'],
                 required=True, require_alternate=True, candidate_count=4)
    return {'short_cases': 14, 'public_candidates': 56,
            'runtime_manifest_sha256': current,
            'bound_manifest_sha256': sha(TARGET),
            'short_only_audit_manifest_sha256': sha(SHORT_ONLY),
            'pinned_receipt_and_candidate_validators_passed': True,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
