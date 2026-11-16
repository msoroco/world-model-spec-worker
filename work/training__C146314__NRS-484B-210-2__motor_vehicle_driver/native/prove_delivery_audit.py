"""Current source-shaped saved-processing delivery boundary test."""
import copy
import json
from pathlib import Path

from audit_delivery import audit

ROOT = Path(__file__).resolve().parents[3]
AID = Path(__file__).resolve().parents[1].name


def rejected(fn, label):
    try:
        fn()
    except (ValueError, KeyError):
        return label
    raise AssertionError('Delivery negative accepted: '+label)


def prove():
    positives = []; negatives = []
    for witness in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            prefix = ROOT/'.runtime-work'/f'c146314-210-2-{witness}-{candidate}-fresh-update061'
            attempt = Path(str(prefix)+'-attempt')
            receipt = json.loads((Path(str(prefix)+'-saved')/'v0001/processing.json').read_text())
            case_id = AID+'__'+witness
            result = audit(attempt, receipt, case_id, candidate)
            assert result['source_shape_passed'] and result['passed'] is False
            positives.append({'case_id':case_id,'candidate_id':candidate,
                              'source_shape_passed':True,'accepted':False})
            altered = copy.deepcopy(receipt)
            altered['original_source_hashes']['native-raw-actors.jsonl'] = '0'*64
            negatives.append(rejected(lambda: audit(attempt, altered, case_id, candidate),
                                      witness+'-'+candidate+'-changed-source'))
            altered = copy.deepcopy(receipt);altered['timestamp_joins']['passed'] = False
            negatives.append(rejected(lambda: audit(attempt, altered, case_id, candidate),
                                      witness+'-'+candidate+'-broken-join'))
            negatives.append(rejected(lambda: audit(attempt, receipt, case_id, candidate,
                                                     pixel_review=attempt/'overview.mkv'),
                                      witness+'-'+candidate+'-diagnostic-pixel-claim'))
    return {'format':'c146314-delivery-diagnostic-proof-v1', 'passed':True,
            'source_shaped_diagnostics':positives,'negative_rejections':negatives,
            'original_native_observed':False,'delivery_acceptance_claimed':False,
            'legal_safety_verdict':None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
