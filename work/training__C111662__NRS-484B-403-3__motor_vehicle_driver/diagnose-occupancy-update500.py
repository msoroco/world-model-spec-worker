"""Pin the first current JSON-adapter U-turn occupancy failure for repair."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=ROOT/'.runtime-work/c111662-update500-selected-matrix/fd302e4b70d8/reference/primary/compatibility/converted'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((BASE/'adapter_report.json').read_text())
trace=json.loads((BASE/'trace.json').read_text())['scenes']
missing=[i for i,scene in enumerate(trace) if scene['subject'] not in scene['occupancy_observed']]
assert missing==list(range(180,205)),missing
for i in missing:
 row=report['occupancy_coverage'][i]
 assert row['tracks'][0]['unresolved']=={'44':['unresolved_grade_separation']}
 assert next(s for s in trace[i]['structures'] if s['id']==44)['kind']=='centre_line'
assert report['atom_coverage']['missing']==['rel.occupies']
assert next(s for s in report['native_centre_lines'] if s['region_id']==44)['road_id']==403
out={'format':'c111662-update500-occupancy-diagnostic-v1','case':'reference','candidate':'primary',
 'manifest_sha256':sha(HERE/'execution-manifest.json'),'adapter_report_sha256':sha(BASE/'adapter_report.json'),
 'trace_sha256':sha(BASE/'trace.json'),'missing_atom':'rel.occupies','missing_frames':missing,
 'unresolved_region_id':44,'unresolved_region_kind':'centre_line','source_road_id':403,
 'observed_cpu_compatibility_passed':False,'original_native_accepted':False}
p=HERE/'update500-occupancy-diagnostic.json';p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'missing_frames':len(missing),'first':missing[0],'last':missing[-1],'diagnostic_sha256':sha(p)}))
