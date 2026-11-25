"""Check the selected path branch's conditional ordinance source gate."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from audit_comparison import audit_selected_pair, AID
from measure_scooter import measure
from prove_scooter import fixture

SOURCE = Path('inputs/coverage/branch-sources.json')
LAW = 'NRS-484B-785-1a'


def reject(root, change, expected):
    context_path = root/'scooter_context.json'
    context = json.loads(context_path.read_text())
    change(context)
    context_path.write_text(json.dumps(context)+'\n')
    try:
        measure(root)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError((expected, str(exc))) from exc
    else:
        raise AssertionError('Unreviewed ordinance source accepted')


def main():
    source = json.loads(SOURCE.read_text())['laws'][LAW]
    law = source['law']['text']
    assert law.startswith('Except as otherwise provided in an ordinance enacted pursuant to NRS 484A.469')
    assert 'On a roadway, bicycle lane, path or route at a speed of not more than 15 miles per hour.' in law
    with tempfile.TemporaryDirectory(prefix='scooter-exception-', dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        fixture(root/'below', 12*.44704, 'controlled_1')
        fixture(root/'at', 15*.44704, 'controlled_at_cap')
        fixture(root/'above', 17*.44704, 'controlled_2')
        measured = [measure(root/name) for name in ('below','at','above')]
        assert all(x['legal_result'] is None and x['fixed_context']['ordinance_exception_reviewed'] is True for x in measured)
        assert all(x['motor_classification_max_mph'] != 15 for x in measured)
        valid = audit_selected_pair(measured[0], measured[1], AID+'__below_vs_requested_at_cap', original_only=False)
        assert valid['fixed_context_checked'] and valid['legal_result'] is None
        changed = json.loads(json.dumps(measured[1]))
        changed['fixed_context']['ordinance_applicability_source'] = 'different ordinance source'
        try:
            audit_selected_pair(measured[0], changed, AID+'__below_vs_requested_at_cap', original_only=False)
        except ValueError as exc:
            assert 'fixed path, device or ordinance' in str(exc)
        else:
            raise AssertionError('Ordinance context changed without separate comparison')
        fixture(root/'missing', 12*.44704, 'controlled_1')
        reject(root/'missing', lambda c:c.pop('ordinance_applicability_source'), 'Missing source-bound context: ordinance_applicability_source')
        fixture(root/'unreviewed', 12*.44704, 'controlled_1')
        reject(root/'unreviewed', lambda c:c.update(ordinance_exception_reviewed=False), 'Path access and ordinance exception not reviewed')
    print(json.dumps({'format':'worker-exception-scope-proof-v1','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'law':LAW,'selected_case_ids':[x['case_id'] for x in measured],
        'result':'conditional exception is source-gated in each selected path case; absent an enacted applicable ordinance source, no distinct legal outcome or replacement speed is inferred',
        'checks':['exact_statutory_clause','reviewed_context_required','applicability_source_required',
            'changed_context_rejected','no_legal_verdict','motor_classification_separate_from_operating_cap']},sort_keys=True))


if __name__=='__main__':
    main()
