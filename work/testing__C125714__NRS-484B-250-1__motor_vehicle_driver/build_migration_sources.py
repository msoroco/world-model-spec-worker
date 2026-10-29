"""AST-only migration002 source builder; never applies edits to exact packages.

migrate_runner returns a capture-only runner and a saved-only prepare_saved
function. The lead alone applies these after the C109705 prototype proof.
"""
import ast, copy

_CONTEXT_KEYS={'geometry','native_landmarks','native_map_name','landmark_ids','cal','surface_authoring','aisle_inventory','context'}

def _call_name(node):
 if not isinstance(node,ast.Call):return None
 return node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None

def _out_path(node):
 if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div) and isinstance(node.left,ast.Name) and node.left.id=='out' and isinstance(node.right,ast.Constant) and isinstance(node.right.value,str):return node.right.value
 return None

def _written_path(stmt):
 if isinstance(stmt,ast.Expr) and isinstance(stmt.value,ast.Call) and isinstance(stmt.value.func,ast.Attribute) and stmt.value.func.attr=='write_text':return _out_path(stmt.value.func.value)
 if isinstance(stmt,ast.With):
  for item in stmt.items:
   call=item.context_expr
   if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='open' and call.args and isinstance(call.args[0],ast.Constant) and any(c in str(call.args[0].value) for c in ('w','x','a')):
    return _out_path(call.func.value)
 return None

def _all_names(nodes,ctx):
 return {n.id for node in nodes for n in ast.walk(node) if isinstance(n,ast.Name) and isinstance(n.ctx,ctx)}

class _RemoveAnalysisImports(ast.NodeTransformer):
 def visit_ImportFrom(self,node):
  if node.module in ('analyze','worker_exchange.media'):
   removed={'finalize'} if node.module=='analyze' else {'compose_four_views'}
   node.names=[n for n in node.names if n.name not in removed]
   if not node.names:return None
  return node

class _ContextRewrite(ast.NodeTransformer):
 def __init__(self):self.required=set()
 def visit_Attribute(self,node):
  node=self.generic_visit(node)
  if node.attr=='name' and isinstance(node.value,ast.Name) and node.value.id=='mapping':
   self.required.add('native_map_name');return ast.Subscript(value=ast.Name(id='saved_context',ctx=ast.Load()),slice=ast.Constant('native_map_name'),ctx=ast.Load())
  return node
 def visit_ListComp(self,node):
  # The old220 tail holds live Landmark objects only to recover their IDs.
  if any(isinstance(g.iter,ast.Name) and g.iter.id=='landmarks' for g in node.generators):
   if not (isinstance(node.elt,ast.Call) and isinstance(node.elt.func,ast.Name) and node.elt.func.id=='str'):
    raise ValueError('Unsupported live-landmark derivation')
   self.required.add('landmark_ids');return ast.Subscript(value=ast.Name(id='saved_context',ctx=ast.Load()),slice=ast.Constant('landmark_ids'),ctx=ast.Load())
  return self.generic_visit(node)


def _preparation_source(statements):
 if not statements:
  return "def prepare_saved(root):\n    return {'status': 'not_required', 'outputs': []}\n"
 statements=copy.deepcopy(statements)
 # Two source observations bracket a course onset. This engineering minimum
 # does not assert100/300ft signaling coverage or any statutory acceptance.
 for stmt in statements:
  for node in ast.walk(stmt):
   if isinstance(node,ast.Compare) and isinstance(node.left,ast.Name) and node.left.id=='onset' and len(node.ops)==1 and isinstance(node.ops[0],ast.Lt) and len(node.comparators)==1 and isinstance(node.comparators[0],ast.Constant) and node.comparators[0].value==2:
    node.comparators[0]=ast.Constant(value=1)
 # The live600a writer previously omitted a field required by its analyzer.
 # Derive it from the preserved actual calibration packet, never a fixture stub.
 has_native_weather=any(isinstance(n,ast.Constant) and n.value=='other_motion.jsonl' for stmt in statements for n in ast.walk(stmt))
 if has_native_weather:
  expanded=[]
  for stmt in statements:
   if _written_path(stmt)=='case_observation.json':
    expanded.extend(ast.parse("packet['visibility_calibration'] = json.loads((out / 'environment_calibration.json').read_text())").body)
   expanded.append(stmt)
  statements=expanded
 rewrite=_ContextRewrite();statements=[rewrite.visit(s) for s in statements]
 stores=_all_names(statements,ast.Store)
 # Function names/nested helper definitions are also locally bound.
 stores|={n.name for stmt in statements for n in ast.walk(stmt) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
 free=_all_names(statements,ast.Load)-stores-{'out','cfg','saved_context'}
 required=sorted((free&_CONTEXT_KEYS)|rewrite.required)
 unsupported=free&{'mapping','world','client','ego','landmarks','actors','camera','capture'}
 if unsupported:raise ValueError('Saved derivation still references live Native state: '+','.join(sorted(unsupported)))
 outputs=[]
 for stmt in statements:
  name=_written_path(stmt)
  if name and name not in outputs:outputs.append(name)
 # The aggregate source is the actual analyzer dependency; obsolete alley
 # context is auxiliary. Other geometry/rule packets stay critical for converter.
 expected=[name for name in outputs if name!='alley_context.json'] if 'case_observation.json' in outputs else outputs
 last_write={_written_path(stmt):i for i,stmt in enumerate(statements) if _written_path(stmt)}
 guarded=[]
 for i,stmt in enumerate(statements):
  name=_written_path(stmt)
  if name and last_write[name]!=i:continue
  if name:
   guard=ast.parse("if not (out / "+repr(name)+").exists():\n    pass").body[0];guard.body=[stmt];stmt=guard
  guarded.append(stmt)
 prelude="""def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
"""
 if expected:
  prelude+="    expected_outputs = "+repr(expected)+"\n    if all((out / p).is_file() for p in expected_outputs):\n        return {'status': 'already_prepared', 'outputs': expected_outputs}\n"
 else:prelude+="    expected_outputs = []\n"
 prelude+="    context_path = out / 'acquisition-context.json'\n    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}\n"
 for name in required:
  if name=='geometry':fallback="out / 'road_geometry.json'"
  elif name=='cal':fallback="out / 'environment_calibration.json'"
  else:fallback=None
  if fallback:
   prelude+="    if "+repr(name)+" not in saved_context and ("+fallback+").is_file():\n        saved_context["+repr(name)+"] = json.loads(("+fallback+").read_text())\n"
  prelude+="    if "+repr(name)+" not in saved_context:\n        raise ValueError('Missing required source: acquisition-context.json:"+name+"')\n"
  prelude+="    "+name+" = saved_context["+repr(name)+"]\n"
 prelude+='\n'.join('    '+line for stmt in guarded for line in ast.unparse(ast.fix_missing_locations(stmt)).splitlines())+'\n'
 prelude+="    return {'status': 'prepared', 'outputs': expected_outputs}\n"
 ast.parse(prelude)
 return prelude


def migrate_runner(code):
 """Return (capture_only_runner_source, saved_preparation_function_source)."""
 tree=ast.parse(code);runs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run']
 if len(runs)!=1:raise ValueError('Exactly one Native run(args) entrypoint is required')
 run=runs[0];cleanup=[(i,n) for i,n in enumerate(run.body) if isinstance(n,ast.Try) and n.finalbody]
 if not cleanup:raise ValueError('Native runner has no guaranteed cleanup block')
 index,capture_try=cleanup[-1];tail=run.body[index+1:]
 if not any(_call_name(n)=='compose_four_views' for stmt in tail for n in ast.walk(stmt)):
  raise ValueError('Runner is already migrated or has no recognized composition tail')
 error_guards=[];derived=[]
 for stmt in tail:
  if isinstance(stmt,ast.If) and isinstance(stmt.test,ast.Name) and stmt.test.id=='errors':error_guards.append(stmt);continue
  if any(_call_name(n) in ('compose_four_views','finalize') for n in ast.walk(stmt)):continue
  if _written_path(stmt)=='four-view-receipt.json':continue
  if isinstance(stmt,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('sources','receipt') for t in stmt.targets):continue
  derived.append(stmt)
 if not error_guards:raise ValueError('Capture must reject recorded Native errors before sealing')
 preparation=_preparation_source(derived)
 # Context is snapshotted before finally closes encoders/destroys actors/restores.
 # If capture fails before this point, the unchanged error guard rejects sealing.
 capture_try.body.extend(ast.parse('saved_context = capture_context(locals())').body)
 run.body.insert(index,ast.parse('saved_context = {}').body[0]);index+=1
 seal=ast.parse("seal_capture(out, frames=frames, restoration=restoration, errors=errors, encoder_exit_codes={name: process.returncode for name, process in encoders.items()}, context=saved_context)").body[0]
 run.body=run.body[:index+1]+error_guards+[seal]
 tree=_RemoveAnalysisImports().visit(tree)
 imports=ast.parse('from worker_exchange.native_output import capture_context, seal_capture').body
 position=1 if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) and isinstance(tree.body[0].value.value,str) else 0
 tree.body[position:position]=imports
 tree=ast.fix_missing_locations(tree);newcode=ast.unparse(tree)+'\n';verify_runner(newcode)
 return newcode,preparation


def verify_runner(code):
 tree=ast.parse(code);run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
 calls=[_call_name(n) for n in ast.walk(run)]
 if any(n in ('compose_four_views','finalize') for n in calls):raise ValueError('Native runner retains saved analysis/composition')
 cleanup=[(i,n) for i,n in enumerate(run.body) if isinstance(n,ast.Try) and n.finalbody][-1]
 tail=run.body[cleanup[0]+1:]
 names=_all_names(tail,ast.Load)
 if names&{'mapping','world','client','ego','actors','landmarks'}:raise ValueError('Live Native object used after cleanup')
 if calls.count('seal_capture')!=1:raise ValueError('Capture seal must be written once')
 before_cleanup=cleanup[1].body
 if not before_cleanup or not any(_call_name(n)=='capture_context' for n in ast.walk(before_cleanup[-1])):raise ValueError('Startup context must be snapshotted before cleanup')
 return {'capture_only':True,'context_before_cleanup':True,'seal_after_cleanup':True,'world_used_after_cleanup':False}
