"""Source-hashed update002 construction and overlay preparation, no Native replay."""
import ast,hashlib,json,pathlib,copy
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,v):p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def overlay_spec():
 base=ROOT/'runtime/main-pipeline-v1';folder=ROOT/'work/_shared/runtime-overlay';baseline=read(base/'SOURCE-MANIFEST.json')['files']
 files=[]
 for p in sorted(folder.rglob('*.py')):
  if '__pycache__' in p.parts:continue
  rel=str(p.relative_to(folder));ast.parse(p.read_text());files.append({'path':rel,'baseline_sha256':baseline[rel],'replacement_sha256':sha(p)})
 write(folder/'overlay.json',{'format':'worker-runtime-overlay-v1','baseline_sha256':sha(base/'SOURCE-MANIFEST.json'),'bootstrap_sha256':sha(ROOT/'work/_shared/runtime002.py'),'files':files,'purpose':'Update002 preserved Native acquisition and revision-selected saved processing; source-derived physical checks, not legal acceptance'})
def assemble_native_output():
 base=(ROOT/'runtime/main-pipeline-v1/scenario_pipeline/worker_exchange/native_output.py').read_text()
 physical=(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/physical_assessment002.py').read_text().split('\ndef _box(')[0]
 left=(ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/migration_left_turn.py').read_text()
 support=(ROOT/'work/_shared/native002_support.txt').read_text().replace("checks,observed=assess_physical(root,cfg,result.get('target_checks',[]))", "assessment=assess_physical(root,cfg,result.get('target_checks',[]));checks=assessment['physical_checks'];observed=assessment['realized_observables']")
 (ROOT/'work/_shared/runtime-overlay/scenario_pipeline/worker_exchange/native_output.py').write_text(base+'\n'+physical+'\n'+left+'\n'+support)

def annotate_analyzer(code,preparation=''):
 if '# update002 selected analyzer' in code:return code
 tree=ast.parse(code)
 # Retain all law-specific calculations, deriving physical flags only from saved observations.
 class Fix(ast.NodeTransformer):
  def visit_Dict(self,node):
   self.generic_visit(node)
   if any(isinstance(k,ast.Constant) and k.value=='maneuver_completed' for k in node.keys):
    pairs=[(k,v) for k,v in zip(node.keys,node.values) if not(isinstance(k,ast.Constant) and k.value in ('setup_confirmed','behavior_attempted','maneuver_completed','realized_observables'))]
    node.keys=[k for k,v in pairs];node.values=[v for k,v in pairs]
   return node
  def visit_Call(self,node):
   self.generic_visit(node)
   if isinstance(node.func,ast.Name) and node.func.id=='write_result' and len(node.args)>=2:
    node.args[1]=ast.Call(func=ast.Name(id='physical_result',ctx=ast.Load()),args=node.args[:2],keywords=[])
   return node
 tree=Fix().visit(tree)
 for statement in tree.body:
  if isinstance(statement,ast.If) and '__name__' in ast.unparse(statement.test):
   for node in ast.walk(statement):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='finalize':node.func.id='finalize_selected'
 if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) and isinstance(tree.body[0].value.value,str):tree.body[0].value.value='Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance.'
 ast.fix_missing_locations(tree);code=ast.unparse(tree)+'\n'
 # Rename only CLI finalization, leaving test imports of law-specific finalizer intact.
 code=code.replace('finalize(Path(a.attempt), Path(a.output))','finalize_selected(Path(a.attempt), Path(a.output))')
 code=code.replace('finalize(Path(args.attempt), Path(args.output))','finalize_selected(Path(args.attempt), Path(args.output))')
 # Functions must exist before the CLI block.
 marker="if __name__ == '__main__':"
 wrapper="\n# update002 selected analyzer\nfrom worker_exchange.native_output import physical_result,finalize_report\n"+preparation+"\ndef finalize_selected(root,output):\n    if (root/'acquisition-context.json').is_file():prepare_saved(root)\n    value=finalize(root,output)\n    finalize_report(root,output)\n    return value\n\n"
 if not preparation:wrapper=wrapper.replace("    if (root/'acquisition-context.json').is_file():prepare_saved(root)\n",'')
 if marker not in code:raise ValueError('No analyzer CLI')
 return code.replace(marker,wrapper+marker)

def snapshot():
 out=ROOT/'.runtime-work/update002/originals';out.mkdir(parents=True,exist_ok=True)
 for p in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  d=out/p.parent.name;d.mkdir(exist_ok=True)
  if not (d/'manifest.json').exists():
   write(d/'manifest.json',read(p));write(d/'result.json',read(p.parent/'result.json'))
   for i,e in enumerate(read(p)['cases']):write(d/('construction-'+str(i)+'.json'),read(p.parent/e['construction']))
 if not (out/'branch-plan.json').exists():write(out/'branch-plan.json',read(ROOT/'work/_shared/branch-coverage.json'))

def update_case(folder,entry,runner,analyzer):
 construction_path=folder/entry['construction'];bundle=read(construction_path);dest=construction_path.parent
 for name,content in [('runner.py',runner),('analyze.py',analyzer)]:
  (dest/name).write_text(content)
  item=next(f for f in bundle['files'] if f['path']==name);item['content']=content;item['source']=str((dest/name).relative_to(ROOT))
 write(construction_path,bundle);entry['construction_sha256']=sha(construction_path)
 for key in ('offline','compatibility','negative','physical_preparation','post_capture'):entry.pop(key,None)
 return entry
if __name__=='__main__':snapshot();assemble_native_output();overlay_spec()
