"""Demote ready CPU returns whose selected manifest predates the pinned runtime."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = REPO/'work'
CURRENT = hashlib.sha256((REPO/'runtime/pipeline/SOURCE-MANIFEST.json').read_bytes()).hexdigest()
BATCH = json.loads((REPO/'batch.json').read_text())


def main():
    if BATCH['runtime']['source_manifest_sha256'] != CURRENT:
        raise ValueError('Frozen batch and current runtime disagree')
    changed = []
    for result_path in sorted(WORK.glob('*/result.json')):
        result = json.loads(result_path.read_text())
        if result.get('status') != 'ready' or result.get('readiness_kind') != 'delivery_prepared':
            continue
        manifest_path = result_path.parent/'execution-manifest.json'
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text())
        previous = manifest.get('runtime_manifest_sha256')
        if previous == CURRENT:
            continue
        old_reason = result['reason']
        result['runtime_cutover_checkpoint'] = {
            'status': 'selected_proofs_historical_reproof_pending',
            'previous_ready_reason': old_reason,
            'previous_runtime_manifest_sha256': previous,
            'current_runtime_manifest_sha256': CURRENT,
            'execution_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'previous_candidate_plans_proven': result.get('candidate_plans_proven'),
            'previous_comparison_audits_passed': result.get('comparison_audits_passed'),
            'previous_strict_gate': result.get('strict_gate'),
            'next_cpu_action': 'Rebind exact selected manifest and regenerate current-runtime offline, positive/negative compatibility, recorded-only saved, physical, delivery and comparison proofs; rerun assignment-scoped strict gate.',
        }
        result['status'] = 'partial'
        result['readiness_kind'] = 'reproof_pending'
        result['candidate_plans_proven'] = 0
        result['comparison_audits_passed'] = 0
        result['reason'] = ('Selected execution manifest binds runtime '+str(previous)+
                            ' but batch pins '+CURRENT+'; prior CPU receipts and strict pass are historical. '
                            'Reprove exact selected candidates and audits under the pinned runtime before restoring ready.')
        if isinstance(result.get('strict_gate'), dict):
            result['strict_gate'] = {'command': result['strict_gate'].get('command'),
                                     'exit_code': None, 'exact_error': 'Current runtime reproof pending',
                                     'historical_strict_gate': True}
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
        changed.append({'assignment_id':result['assignment_id'], 'previous_runtime_manifest_sha256':previous,
                        'current_runtime_manifest_sha256':CURRENT})
    return {'format':'runtime-cutover-ready-demotion-v1', 'count':len(changed),
            'current_runtime_manifest_sha256':CURRENT, 'assignments':changed}


if __name__=='__main__':
    print(json.dumps(main(), indent=2, sort_keys=True))
