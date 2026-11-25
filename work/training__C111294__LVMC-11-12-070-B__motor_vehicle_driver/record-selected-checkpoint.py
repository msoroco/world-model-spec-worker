"""Record the exact selected CPU checkpoint without changing partial readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'execution-manifest.json'
    comparison = HERE / 'selected-comparison-audit.json'
    antecedent = HERE / 'selected-antecedent-audit.json'
    manifest_data = json.loads(manifest.read_text())
    result_path = HERE / 'result.json'
    result = json.loads(result_path.read_text())
    result['selected_cpu_checkpoint'] = {
        'status': 'selected_exact_pair_validators_passed_pending_full_statutory_branches',
        'execution_manifest': manifest.name,
        'execution_manifest_sha256': sha(manifest),
        'selected_case_ids': [e['case_id'] for e in manifest_data['cases']],
        'candidate_count_per_case': 2,
        'selected_fallback_compatibility_receipts': {
            e['case_id']: e['candidates'][0]['compatibility']['sha256']
            for e in manifest_data['cases']},
        'physical_cpu_receipts': {
            e['case_id']: e['physical_preparation']['sha256']
            for e in manifest_data['cases']},
        'delivery_cpu_positive_negative_logs': {
            e['case_id']: [e['delivery_acceptance']['test_log_sha256'],
                           e['delivery_acceptance']['negative_log_sha256']]
            for e in manifest_data['cases']},
        'comparison_audit': comparison.name,
        'comparison_audit_sha256': sha(comparison),
        'selected_antecedent_audit': antecedent.name,
        'selected_antecedent_audit_sha256': sha(antecedent),
        'original_native_observed': False,
        'legal_acceptance_claimed': False,
    }
    result['candidate_count'] = sum(1 + len(e['candidates']) for e in manifest_data['cases'])
    result['reason'] = ('Two exact selected cases now bind source-hashed primary and upstream-spawn '
                        'fallback constructions, current-runtime offline and public compatibility, '
                        'recorded-only saved, three-outcome physical CPU fixtures, independent '
                        'delivery positive/negative audits, canonical semantic and fixed-condition '
                        'comparison and source-antecedent proofs. Current-runtime selected execution, semantic, delivery '
                        'and compatibility validators pass. The assignment remains partial because '
                        'the full statutory alternatives and complete handoff are unfinished; '
                        'original Native physical and legal review is pending.')
    result['status'] = 'partial'
    result['readiness_kind'] = 'implementation_checkpoint'
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    handoff = HERE / 'HANDOFF.md'
    heading = '## 2026-11-25 selected exact-case CPU binding'
    paragraph = (
        f'{heading}\n\n'
        'The two canonical cases `__probe_1` and `__probe_2` now appear as selected '
        'delivery entries in `execution-manifest.json`, with their previously proved '
        'primary constructions and one source-triggered upstream-spawn `fallback1` each. '
        'Both newly bound fallback public compatibility runs passed full 600-frame '
        'four-view Native/Core/Lean/decode and missing-road rejection. Source-bound '
        'three-outcome physical CPU fixtures passed for both cases, as did independent '
        'selected diagnostic delivery positives and original-source-required negatives. '
        '`prove-selected-antecedent.py` binds both selected public measurements to '
        'a 140-frame prior stop and the about-to-enter first frame while expressly '
        'leaving lawful prior yield unresolved. '
        '`prove-selected-comparison.py` verified fixed entrant and road source, the '
        'through-response contrast and changed-road/entrant negative mutations. '
        f'Execution manifest SHA-256 `{sha(manifest)}`; selected comparison proof SHA-256 '
        f'`{sha(comparison)}`; selected antecedent proof SHA-256 `{sha(antecedent)}`. '
        'These software fixtures do not establish original Native '
        'motion, pixels, lawful prior yield or a legal verdict. Finish full statutory '
        'alternatives and complete assignment handoff, then run the exact scoped strict '
        'gate before ready. Current status: partial.\n')
    current = handoff.read_text()
    if heading in current:
        current = current.split(heading, 1)[0].rstrip() + '\n'
    handoff.write_text(current.rstrip() + '\n\n' + paragraph)


if __name__ == '__main__':
    main()
