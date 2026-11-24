"""Execute positive and altered actor-source branch diagnostics."""
import hashlib
import json
import os
from pathlib import Path

from audit_sources import HERE, audit
from audit_comparisons import run as compare

BASE = HERE.parent
REPO = BASE.parents[1]
SCRATCH = REPO/'.runtime-work/c111294-2502-branch-negative'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def prove():
    if not str(SCRATCH.resolve()).startswith(str((REPO/'.runtime-work').resolve())):
        raise ValueError('Temporary branch probe outside runtime scratch')
    SCRATCH.mkdir(parents=True,exist_ok=True)
    positive = []
    for suffix in ('device_controlled','opposing_no_turn','opposing_left_turn'):
        positive.append(audit(suffix))
    comparison = compare()
    source = HERE/'opposing_left_turn/sources/actor-history.json'
    corrupted = json.loads(source.read_text())
    corrupted['rows'][120]['other']['center_xyz_m'][0] += 1
    probe = SCRATCH/'altered-actor-history.json'
    write(probe,corrupted)
    try:
        audit('opposing_left_turn',probe)
    except ValueError as error:
        if 'source join' not in str(error):
            raise
        negative = str(error)
    else:
        raise ValueError('Altered actor source was accepted')
    receipt = {'format':'c111294-2502-branch-source-proof-v1',
               'positive':positive,
               'comparison_sha256':sha(HERE/'comparison-audit.json'),
               'comparisons':comparison,
               'negative_error':negative,
               'negative_source_sha256':sha(probe),
               'negative_scratch_only':True,
               'original_native_observed':False,
               'legal_verdict':None}
    path=HERE/'source-proof.json'
    write(path,receipt)
    print(json.dumps({'source_proof_sha256':sha(path),
                      'positive_cases':len(positive),'negative_rejected':True},sort_keys=True))


if __name__=='__main__':
    prove()
