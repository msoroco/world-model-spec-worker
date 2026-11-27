"""CPU diagnostic source-join proof for all A2 loading-stop comparisons."""
import copy
import json
from pathlib import Path
from comparison_audit import audit_comparison,sha

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SCRATCH=REPO/'.runtime-work/c378132-a2'


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    reports={};hashes={}
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        original=SCRATCH/('compat-'+suffix+'-v3')/'analysis-report.json'
        saved=ROOT/'cases'/suffix/'diagnostic-analysis-report.json'
        saved.write_bytes(original.read_bytes())
        compat=json.loads((ROOT/'cases'/suffix/'primary-compatibility.json').read_text())
        if sha(saved)!=compat['analysis_report_sha256']:
            raise ValueError('analysis report differs from positive compatibility receipt')
        reports[case['case_id']]=json.loads(saved.read_text());hashes[suffix]=sha(saved)
    audited=[]
    for comparison in plan['comparisons']:
        pair={case_id:reports[case_id] for case_id in comparison['case_ids']}
        accepted=audit_comparison(comparison,pair,diagnostic=True)
        audited.append(accepted)
        broken=copy.deepcopy(pair)
        second=comparison['case_ids'][1]
        field=accepted['observed_difference']
        broken[second]['observation'][field]=broken[comparison['case_ids'][0]]['observation'][field]
        try:audit_comparison(comparison,broken,diagnostic=True)
        except ValueError as error:
            if 'observed A2 loading-stop condition differs' not in str(error):raise
        else:raise ValueError('negative comparison accepted changed observed contrast')
    receipt={'format':'worker-diagnostic-comparison-audit','assignment_id':ROOT.name,
             'passed':True,'scope':'source-hashed synthetic CPU fixtures only; no physical or legal acceptance',
             'comparison_ids':[row['comparison_id'] for row in audited],
             'analysis_report_sha256':hashes,'audits':audited}
    (ROOT/'comparison-audit.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(f"{len(audited)} source-bound A2 comparisons and changed-observation negatives passed")


if __name__=='__main__':main()
