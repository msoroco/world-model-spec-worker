"""Bind frozen intersection parking topics to current unselected CPU evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LAW='NRS-484B-450-1c'
PROOFS=('draft-execution-manifest.json','pinned-offline-proof.log',
        'draft-package-audit.json','portable-matrix-audit.log',
        'measurement-contract-audit.log','synthetic-pair-audit.log',
        'synthetic-trigger-crossings.json','synthetic-trigger-crossings-audit.log')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen=read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan=read(HERE/'case-plan.json')
    matrix_path=ROOT/'work/_shared/branch-coverage.json'
    matrix=read(matrix_path)
    review=read(ROOT/'work/_shared/branch-review.json')
    branches=matrix['laws'][LAW]['branches']
    branch=next(b for b in branches if b['branch_id'].startswith('intersection_stop_stand_park__'))
    cases={c['case_id'] for c in plan['cases']}
    comparison=plan['comparisons'][0]
    if (set(branch['topic_ids'])!=set(frozen['topics']) or branch['status']!='runnable' or
        branch['assignment_id']!=HERE.name or set(branch['case_ids'])!=cases or
        branch['comparison_ids']!=[comparison['comparison_id']] or
        set(comparison['case_ids'])!=cases or
        any(b['status']!='pending_review' for b in branches if b is not branch)):
        raise ValueError('Frozen statutory branch or exceptions differ')
    if branch['cpu_proofs']!={name:sha(HERE/name) for name in PROOFS}:
        raise ValueError('CPU proof hashes differ')
    if review['coverage_sha256']!=sha(matrix_path) or LAW not in review['missing_branches']:
        raise ValueError('Branch review/missing exceptions differ')
    result=read(HERE/'result.json')
    if result['status']!='blocked' or result['readiness_kind'] is not None:
        raise ValueError('Unselected assignment status differs')
    manifest=read(HERE/'draft-execution-manifest.json')
    triggers=read(HERE/'synthetic-trigger-crossings.json')
    package=read(HERE/'draft-package-audit.json')
    if (manifest['status']!='draft_not_selected' or len(manifest['cases'])!=2 or
        not triggers['passed'] or len(triggers['rows'])!=8 or
        triggers['original_native_or_pixels_observed'] or
        not package['passed']):
        raise ValueError('Exact draft or synthetic trigger/package proof differs')
    for script in ('audit-synthetic-pair.py','audit-measurement-contracts.py',
                   'audit-draft-package.py','audit-portable-matrix.py',
                   'audit-synthetic-trigger-crossings.py'):
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,
                       check=True,capture_output=True,text=True)
    receipt={'passed':True,'law_id':LAW,'branch_id':branch['branch_id'],
             'source_topics':sorted(frozen['topics']),'controlled_cases':sorted(cases),
             'exact_offline_bundles':8,'v1_positive_negative_pairs':8,
             'synthetic_frames_per_case':480,'measured_trigger_crossings_per_case':3,
             'pending_exception_branches':3,'selected':False,
             'original_native_or_strict_v2_verified':False,
             'proof_sha256':branch['cpu_proofs']}
    (HERE/'parking-cpu-branch-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':main()
