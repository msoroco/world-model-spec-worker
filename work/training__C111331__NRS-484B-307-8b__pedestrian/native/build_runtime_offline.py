"""Bind unselected facing-red entry/no-entry source drafts to pinned runtime."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ASSIGNMENT=HERE.parent
ROOT=ASSIGNMENT.parents[1]
FROZEN=ROOT/'inputs'/ASSIGNMENT.name/'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


CHECK='''"""Check copied statutory and red-entry source identities."""
import json
from pathlib import Path
from red_entry import measure,requested,sha

HERE=Path.cwd()

def check():
    cfg=json.loads((HERE/'config.json').read_text())
    frozen=json.loads((HERE/'assignment-source.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    if (sha(HERE/'assignment-source.json')!=cfg['frozen_sha256'] or
        sha(HERE/'case-plan.json')!=cfg['plan_sha256'] or
        sha(HERE/'red-entry-source.jsonl')!=cfg['source_sha256'] or
        sha(HERE/'red-entry-context.json')!=cfg['context_sha256'] or
        frozen['law']['text']!=plan['source_law']['text'] or
        frozen['cell']['cell_id']!='C111331'):
        raise ValueError('Copied red-entry statutory/source identity changed')
    rows=[json.loads(line) for line in (HERE/'red-entry-source.jsonl').read_text().splitlines()]
    if rows!=requested(cfg['condition']):
        raise ValueError('Exact red-entry request changed')
    result=measure(HERE/'red-entry-source.jsonl',HERE/'red-entry-context.json')
    if result['condition']!=cfg['condition']:
        raise ValueError('Red-entry condition changed')
    return result

if __name__=='__main__':
    print(json.dumps(check()))
'''
TEST='''import unittest
from check import check

class ExactRedEntry(unittest.TestCase):
    def test_source(self):
        row=check()
        self.assertEqual(row['frames'],600)
        self.assertEqual(row['rate_hz'],20)
        self.assertFalse(row['signal_authority_native_verified'])
        self.assertFalse(row['legal_verdict_claimed'])
'''


def main():
    plan=ASSIGNMENT/'case-plan.json'
    frozen=json.loads(FROZEN.read_text())
    planned=json.loads(plan.read_text())
    if frozen['law']['text']!=planned['source_law']['text']:
        raise ValueError('Frozen red-entry law changed')
    entries=[]
    for index,condition in enumerate(('condition_a','condition_b')):
        source=ASSIGNMENT/'diagnostic-red-entry'/(condition+'.jsonl')
        context=ASSIGNMENT/'diagnostic-red-entry/context.json'
        cases=[case['case_id'] for case in planned['cases'] if case['condition_index']==index]
        if len(cases)!=1:
            raise ValueError('Planned condition missing')
        cfg={'case_id':cases[0],'condition':condition,'candidate_id':'primary',
             'frozen_sha256':sha(FROZEN),'plan_sha256':sha(plan),
             'source_sha256':sha(source),'context_sha256':sha(context),
             'frames':600,'rate_hz':20,'duration_s':30,
             'selected':False,'original_native_observed':False}
        files=[{'path':name,'content':content} for name,content in (
            ('assignment-source.json',FROZEN.read_text()),
            ('case-plan.json',plan.read_text()),
            ('red-entry-source.jsonl',source.read_text()),
            ('red-entry-context.json',context.read_text()),
            ('red_entry.py',(HERE/'red_entry.py').read_text()),
            ('check.py',CHECK),('tests/test_exact.py',TEST),
            ('config.json',json.dumps(cfg,indent=2)+'\n'))]
        construction={'case_id':cases[0],'cell_id':'C111331',
                      'law_id':'NRS-484B-307-8b','actor':'pedestrian',
                      'entrypoint':'check.py','files':files,
                      'status':'unselected_cpu_diagnostic',
                      'recording_description':'Authored 30-second facing-red pedestrian entry request; Native signal authority and other-device exception unverified.'}
        target=HERE/'runtime-drafts'/condition/'construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(construction,indent=2)+'\n')
        entries.append({'case_id':cases[0],
                        'construction':str(target.relative_to(HERE)),
                        'construction_sha256':sha(target),'candidates':[],
                        'candidate_risk':{'status':'physical',
                          'reason':'Governing signal head, pedestrian path and other-device exception unverified in Native.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ASSIGNMENT.name,'status':'draft_not_selected',
              'cases':entries,'original_native_observed':False,
              'delivery_ready':False}
    target=HERE/'draft-execution-manifest.json'
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':len(entries),'manifest_sha256':sha(target)}))


if __name__=='__main__':
    main()
