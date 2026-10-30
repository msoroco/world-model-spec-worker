"""Build exact comparison indexes from completed saved-only processing receipts."""
import argparse
import json
from pathlib import Path

def read(path): return json.loads(path.read_text())

def build(repo,processed_root):
    repo=Path(repo).resolve();processed_root=Path(processed_root).resolve();count=0
    for manifest_path in sorted((repo/'work').glob('testing__*/execution-manifest.json')):
        manifest=read(manifest_path);aid=manifest['assignment_id'];index={}
        for entry in manifest['cases']:
            cid=entry['case_id'];output=processed_root/aid/cid
            options=[]
            for path in output.glob('v*/processing.json'):
                receipt=read(path)
                allowed={entry['construction_sha256']}|{c['construction_sha256'] for c in entry.get('candidates',[])}
                if (receipt.get('case_id')==cid and receipt.get('passed') is True
                        and receipt.get('analysis_revision',{}).get('construction_sha256') in allowed
                        and receipt.get('analysis_revision',{}).get('runtime_manifest_sha256')==manifest['runtime_manifest_sha256']
                        and receipt.get('originals_preserved') is True):
                    options.append((path,receipt))
            if not options: raise ValueError('No exact saved analysis version for '+cid)
            path,receipt=max(options,key=lambda row:row[0].parent.name)
            stage=Path(receipt['analysis_directory']).resolve()
            if not (stage/'analysis-report.json').is_file() or not (stage/'config.json').is_file():
                raise ValueError('Saved analysis source missing for '+cid)
            index[cid]={'analysis_report':str(stage/'analysis-report.json'),
                        'config':str(stage/'config.json'),'processing_receipt':str(path),
                        'native_revision':receipt['native_revision'],
                        'analysis_revision':receipt['analysis_revision']}
            count+=1
        destination=processed_root/aid/'native-comparison-index.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(index,indent=2)+'\n')
    return {'cases_indexed':count,'assignments':len(list((repo/'work').glob('testing__*/execution-manifest.json')))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--processed-root',type=Path,required=True);args=p.parse_args()
    print(json.dumps(build(args.repo,args.processed_root),indent=2))
if __name__=='__main__':main()
