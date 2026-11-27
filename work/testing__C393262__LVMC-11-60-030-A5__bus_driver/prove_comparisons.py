"""Independent source-bound CPU comparison of bus duration boundaries."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    reports = {}
    configs = {}
    hashes = {}
    for case in plan['cases']:
        suffix = case['case_id'].split('__')[-1]
        source = REPO/'.runtime-work/c393262-bus'/('compat-'+suffix+'-v2')/'analysis-report.json'
        saved = ROOT/'cases'/suffix/'diagnostic-analysis-report.json'
        saved.write_bytes(source.read_bytes())
        compatibility = json.loads((ROOT/'cases'/suffix/'primary-compatibility.json').read_text())
        if sha(saved) != compatibility['analysis_report_sha256']:
            raise ValueError('analysis report differs from source-bound receipt: '+suffix)
        report = json.loads(saved.read_text())
        if report['case_id'] != case['case_id'] or report['legal_verdict'] is not None:
            raise ValueError('wrong case or legal verdict: '+suffix)
        reports[suffix] = report
        hashes[suffix] = sha(saved)
        construction = json.loads((ROOT/'cases'/suffix/'construction.json').read_text())
        configs[suffix] = json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))

    def duration(suffix):
        return reports[suffix]['measurements']['duration_relation']['value']['observed_duration_s']

    def designation(suffix):
        return reports[suffix]['measurements']['duration_relation']['value']['applicable_designated_duration_s']

    for conduct in ('park','stand'):
        samples = [duration(conduct+'_'+relation) for relation in ('below','at','above')]
        designated = [designation(conduct+'_'+relation) for relation in ('below','at','above')]
        if samples != [13,15,17] or designated != [15,15,15]:
            raise ValueError('source-measured D-relative duration sweep collapsed: '+conduct)
        if [configs[conduct+'_'+relation]['case']['conduct'] for relation in ('below','at','above')] != [conduct]*3:
            raise ValueError('conduct comparison variable changed')
    for relation in ('below','at','above'):
        if duration('park_'+relation) != duration('stand_'+relation):
            raise ValueError('stand versus park duration changed')
    ids = [item['comparison_id'] for item in plan['comparisons']]
    if ids != ['park_duration_boundary','stand_duration_boundary','stand_versus_park_at']:
        raise ValueError('three selected comparison IDs differ')
    receipt = {'format':'worker-diagnostic-comparison-audit', 'assignment_id':ROOT.name,
               'passed':True, 'scope':'source-hashed synthetic CPU fixtures only; no legal or physical acceptance',
               'comparison_ids':ids, 'analysis_report_sha256':hashes,
               'diagnostic_D_s':15, 'park_duration_s':[13,15,17], 'stand_duration_s':[13,15,17],
               'remaining':['original stop-specific designation and boundary review',
                            'original Native bus/camera source review and physical completion',
                            'independent standing or parking and legal judgment']}
    (ROOT/'comparison-audit.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('three source-bound bus duration comparisons passed; synthetic CPU only')


if __name__ == '__main__':
    main()
