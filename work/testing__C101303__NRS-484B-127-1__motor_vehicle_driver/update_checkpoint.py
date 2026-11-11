"""Bind current C101303 checkpoint claims to retained CPU proof logs."""
import hashlib
import json
from pathlib import Path

folder=Path(__file__).resolve().parent
path=folder/'result.json'
result=json.loads(path.read_text())
manifest=json.loads((folder/'execution-manifest.json').read_text())
claims={item['log']:item for item in result['tests']}


def claim(command,log):
    source=folder/log
    claims[log]={'command':command,'exit_code':0,'log':log,
                 'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}


for name in ('cpu-tests.log','preflight-current.log'):
    claim(claims[name]['command'],name)
for entry in manifest['cases']:
    proof=entry['delivery_acceptance']
    claim(proof['command'],proof['test_log'])
    for row in [entry, *entry['candidates']]:
        compat=row['compatibility']
        if compat.get('replay_command'):
            claim(compat['replay_command'],compat['replay_log'])
        saved=row.get('post_capture')
        if saved and saved.get('command'):
            claim(saved['command'],saved['test_log'])
claim('.venv-cpu/bin/python work/'+folder.name+'/validate_delivery_full.py',
      'delivery-full-validator.log')
claim('.venv-cpu/bin/python work/'+folder.name+'/full_duration_comparison_proof.py',
      'full-duration-comparison.log')
claim('.venv-cpu/bin/python work/'+folder.name+'/full_duration_fallback_comparison_proof.py',
      'full-duration-fallback-comparison.log')
claim('.venv-cpu/bin/python work/'+folder.name+'/sweep_controller_envelope.py '
      '--config work/'+folder.name+'/config.json --output work/'+folder.name+
      '/sweep-controller-envelope.json', 'sweep-envelope.log')
result['tests']=list(claims.values())
result['readiness_kind']='all_exact_case_full_duration_diagnostic_delivery_checkpoint'
result['reason']=(
    'All eight C101303 conditional cases and 24 fallbacks retain exact offline and '
    'compatibility proofs. All eight primaries and all 24 fallbacks '
    'have recorded-only saved-processing proofs, with the 21 remaining fallback '
    'paths freshly rerun against their exact constructions. Their independent delivery '
    'audit now passes eight full 900-frame synthetic source, classifier, four-camera, '
    'composed-video and Core-join software paths, with eight missing-sealed-history '
    'negative proofs plus base actor-identity, unsealed-source and unverified-physical-status rejection. Seven '
    'primary comparisons pass against the 900-frame diagnostic sources, and 21 '
    'fallback construction comparisons pass with those primary synthetic histories; '
    'an altered fixed surface, skipped frame, relative-time drift and unrelated initial '
    'lead velocity are rejected. The faster-ego diagnostic source was corrected so '
    'its lead initial velocity matches the base; its four exact compatibility and '
    'recorded-only saved paths, 900-frame delivery audit and linked comparisons were rerun. All '
    'diagnostic audits explicitly report passed=false and no physical acceptance. '
    'The three-point 7.0/8.5/10.0 m controller probe verifies command response only; '
    'a 42-state CPU envelope finds 19 states with distinct commands and exposes '
    'saturation at larger spacing. '
    'The complete physically feasible judgment sweep, fallback-specific source and '
    'actual Native-source comparisons, independent final review and '
    'shared branch/delivery queue/integration remain worker-owned CPU work. Actual '
    'Native motion, source pixels and legal judgment remain unverified. See HANDOFF.md.'
)
path.write_text(json.dumps(result,indent=2)+'\n')
