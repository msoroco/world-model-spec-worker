"""Select latest source-matching saved analysis versions; never replay Native."""
import json,pathlib,shlex
ROOT=pathlib.Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def main():
 for path in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  m=read(path);index={}
  for entry in m['cases']:
   args=shlex.split(entry['post_capture']['command']);output=ROOT/args[args.index('--output')+1];matches=[]
   for p in output.glob('v*/processing.json'):
    r=read(p)
    if r['case_id']==entry['case_id'] and r['analysis_revision']['construction_sha256']==entry['construction_sha256']:matches.append((p,r))
   if not matches:raise ValueError('No current saved analysis version for '+entry['case_id'])
   p,r=max(matches,key=lambda v:v[0].parent.name);stage=pathlib.Path(r['analysis_directory']);index[entry['case_id']]={'analysis_report':str(stage/'analysis-report.json'),'config':str(stage/'config.json'),'processing_receipt':str(p),'native_revision':r['native_revision'],'analysis_revision':r['analysis_revision']}
  (path.parent/'native-comparison-index.json').write_text(json.dumps(index,indent=2)+'\n')
if __name__=='__main__':main()
