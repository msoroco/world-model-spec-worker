"""Independently bind every exact three-fallback construction and CPU receipt."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


MANIFESTS=(
    'probe-compatibility-manifest.json',
    'probe-compatibility-west-manifest.json',
    'probe-compatibility-left-manifest.json',
    'probe-compatibility-closure-manifest.json',
    'probe-compatibility-passing-manifest.json',
    'probe-compatibility-narrow-manifest.json',
    'probe-compatibility-one-way-manifest.json',
    'probe-compatibility-three-lane-manifest.json',
)


def audit(root):
    root=Path(root)
    repo=root.parents[1]
    sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
    from worker_exchange.candidate_constructions import validate
    results=[]
    for name in MANIFESTS:
        path=root/name
        manifest=json.loads(path.read_text())
        entry=manifest['cases'][0]
        result=validate(root,entry,'NRS-484B-200-1','C125714',required=True,
                        require_alternate=True,candidate_count=4)
        primary=json.loads((root/entry['construction']).read_text())
        files={item['path']:item['content'] for item in primary['files']}
        runner=primary['entrypoint']
        changes=[]
        for candidate in entry['candidates']:
            selected=json.loads((root/candidate['construction']).read_text())
            alternate={item['path']:item['content'] for item in selected['files']}
            changed={key for key in files if files[key]!=alternate[key]}
            if candidate['id']=='fallback2' and runner=='native_passing_probe.py':
                expected={'passing_construction.py'}
            else:
                expected={runner}
            if changed!=expected:
                raise ValueError('Fallback changed unexpected implementation file: '+name+'/'+candidate['id'])
            if candidate['id']=='fallback1' and 'route[1].transform)' not in alternate[runner]:
                raise ValueError('Spawn fallback lacks second connected waypoint')
            if candidate['id']=='fallback2' and not (
                    'target_speed_mps=3.5' in alternate[runner] or
                    'target_speed_mps=6.0' in alternate.get('passing_construction.py','')):
                raise ValueError('Speed fallback lacks controller change')
            if candidate['id']=='fallback3' and 'min(3 + index // 8' not in alternate[runner]:
                raise ValueError('Progress fallback lacks lookahead change')
            changes.append({'id':candidate['id'],'changed_files':sorted(changed),
                            'construction_sha256':candidate['construction_sha256']})
        results.append({'case_id':entry['case_id'],'manifest':name,
                        'manifest_sha256':sha256(path.read_bytes()).hexdigest(),
                        'validated_fallbacks':result['fallbacks'],'changes':changes})
    return {'format':'worker-c125714-fallback-audit','cases':results,
            'exact_offline_and_compatibility_verified':True,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    Path(args.output).write_text(json.dumps(audit(root),indent=2)+'\n')


if __name__=='__main__':main()
