"""Run independent exact-package CPU proof queues with strict retained-frame joins."""
import concurrent.futures,importlib.util,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER=Path(__file__).parent
sp=importlib.util.spec_from_file_location('p3',OWNER/'build_partition_packages.py');P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
os.environ['TMPDIR']=str(ROOT/'.runtime-work/tmp');os.environ['MPLCONFIGDIR']=str(ROOT/'.runtime-work/mpl');os.environ['XDG_CACHE_HOME']=str(ROOT/'.runtime-work/cache')
for name in ['tmp','mpl','cache']:(ROOT/'.runtime-work'/name).mkdir(exist_ok=True)
specs=[P.prepare_113(),P.prepare_407(),P.prepare_127(False),P.prepare_127(True)]+[P.prepare_257(law,control) for law in ['NRS-484B-257-1','NRS-484B-257-2'] for control in ['yield','stop','officer','signal']]
# All law-specific diagnostic frame identities and times join the unchanged retained fixture.
mapping={r['carla_frame']:r['time_s'] for r in map(json.loads,(ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed/video_frames.jsonl').read_text().splitlines())}
for spec in specs:
 for case in spec['cases']:
  assert case['config'].get('cell_id',spec['assignment_id'].split('__')[1])==spec['assignment_id'].split('__')[1]
  for name,value in case['fixture'].items():
   if name.endswith('.jsonl'):
    for row in map(json.loads,value.splitlines()):assert row['frame'] in mapping and abs(row['time_s']-mapping[row['frame']])<1e-12,(spec['assignment_id'],name,row)
for spec in specs:
 P.B.write(OWNER/('package-spec-'+spec['assignment_id'].split('__')[1]+'-'+spec['assignment_id'].split('__')[2]+'.json'),spec)
 P.B.build(spec)
print('Validated all exact diagnostic joins; built '+str(sum(len(s['cases']) for s in specs))+' exact cases.',flush=True)
def prove(spec):
 folder=ROOT/'work'/spec['assignment_id'];P.B.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck');print('PROVED '+spec['assignment_id']+' '+str(len(spec['cases'])),flush=True);return spec['assignment_id']
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures=[pool.submit(prove,s) for s in specs]
 for future in concurrent.futures.as_completed(futures):future.result()
print('ALL92 EXACT CASES PROVED; Native executed0.',flush=True)
