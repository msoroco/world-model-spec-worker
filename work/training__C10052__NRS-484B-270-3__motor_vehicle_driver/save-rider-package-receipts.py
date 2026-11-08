"""Retain exact unselected v1 package receipts outside ignored scratch."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=HERE/'rider-package-matrix-summary.json'
    matrix=json.loads(source.read_text())
    if matrix.get('passed') is not True or len(matrix.get('results',[]))!=24:
        raise ValueError('Complete 24-candidate package matrix required')
    rows=[]
    for item in matrix['results']:
        suffix=item['case_id'].rsplit('__',1)[-1]
        candidate=item['candidate_id']
        output=ROOT/item['positive']
        target=HERE/'draft-rider-cases'/suffix/candidate
        files=(('compatibility.json','package-receipt.json'),
               ('analysis-report.json','package-report.json'),
               ('result.json','package-result.json'),
               ('compatibility-analysis.log','package-analysis.log'))
        retained={}
        for name,destination in files:
            source_file=output/name
            if not source_file.is_file():raise ValueError('Missing package source '+name)
            path=target/destination
            shutil.copyfile(source_file,path)
            retained[destination]=sha(path)
        negative=target/'package-negative.log'
        shutil.copyfile(ROOT/item['negative_log'],negative)
        retained[negative.name]=sha(negative)
        if retained['package-receipt.json']!=item['positive_receipt_sha256'] or \
           retained['package-report.json']!=item['analysis_report_sha256'] or \
           retained['package-result.json']!=item['result_sha256'] or \
           retained['package-negative.log']!=item['negative_log_sha256']:
            raise ValueError('Retained exact receipt differs from package matrix')
        rows.append({'case_id':item['case_id'],'candidate_id':candidate,
                     'construction_sha256':item['construction_sha256'],
                     'retained':retained})
    summary={'format':'c10052-retained-rider-v1-receipts-v1','passed':True,
        'matrix_sha256':sha(source),'rows':rows,
        'scope':'unselected synthetic v1 package compatibility; no strict v2 or original Native capture',
        'selected':False,'accepted':False}
    path=HERE/'rider-package-saved-receipts.json'
    path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'passed':True,'receipts':len(rows),'summary_sha256':sha(path)},indent=2))


if __name__=='__main__':main()
