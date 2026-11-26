import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
manifest = HERE / 'execution-manifest.json'
result_path = HERE / 'result.json'
result = json.loads(result_path.read_text())
result['status'] = 'partial'
result['reason'] = ('Six exact selected Native primary cases pass current-v2 offline and public positive/missing-source negative compatibility. '
                    'Six recorded-only saved receipts, six physical/lifecycle diagnostic proofs, six independent delivery selftests, '
                    'five semantic judgments and five controlled comparison audits are bound. One physical-risk fallback per case '
                    'is under public compatibility proof. Original Native cane appearance, blindness, assistance and legal outcome '
                    'remain unverified; exact scoped strict gate has not passed.')
result['planned_case_count'] = 6
result['candidate_count'] = 6
result['unresolved_branch_count'] = 0
result['accepted_membership_count'] = 0
result['current_v2_package_checkpoint'] = {
    'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
    'primary_offline_passed': 6,
    'primary_compatibility_passed': 6,
    'recorded_only_saved_passed': 6,
    'fallback_offline_passed': 6,
    'fallback_compatibility_passed': 0,
    'semantic_judgments': 5,
    'controlled_comparisons': 5,
    'physical_delivery_cpu_proofs': 6,
    'original_native_acceptance_claimed': False,
}
result_path.write_text(json.dumps(result, indent=2) + '\n')

handoff = HERE / 'HANDOFF.md'
body = handoff.read_text().rstrip()
body += '''

## 2026-11-25 selected full-law CPU package checkpoint

The selected six-case plan covers the red-tipped cane stop/no-stop contrast, wholly versus partially blind white-cane context, assisted-person context, and premature post-stop release. Five source-listed requirement dispositions map to retained original pose, camera, road and blind-person context sources. The comparisons retain their fixed mountain-road cell and declare exactly one intended source or driver-control request difference. They are diagnostic controls, not original Native outcomes or legal verdicts.

Each of the six exact primary inline constructions passed current-v2 `runtime.py offline` and public `runtime.py compatibility` positive and missing-source negative checks. Each case also passed recorded-only `runtime.py process-saved` on its synthetic source-shaped capture, and its processing receipt is hash-bound under `saved/`. Six physical completion/lifecycle fixture sets and independent positive/negative delivery acceptance tests are bound. Five semantic judgment proposals and five controlled comparison diagnostic audits are present. These CPU results do not establish physical cane marker visibility, actual blindness, assistance, full stopping, or injury-avoidance precautions in an original Native capture.

The physical risk is that authored debug cane strokes or assistant actor and requested stop/release may not appear or realize as intended in original four-camera source. One case-preserving fallback per selected case increases the authored cane stroke thickness; its trigger is original source-frame visibility. All six fallbacks passed `runtime.py offline`. Public compatibility and exact scoped strict validation remain in progress. Status stays `partial`; accepted original recording membership remains zero.
'''
handoff.write_text(body.rstrip() + '\n')
print(result['current_v2_package_checkpoint'])
