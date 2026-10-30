"""Build the supplied full Core in isolation and validate JSON with Lean itself.

No law registry, generated rule, or source library is modified. The executable
checks decoding, manifest completeness and same-scene identity references only.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from .adapter import full_core

VALIDATOR = '''import Std.Data.HashSet
import Std.Data.HashMap
import TrafficSpec.Core.Runtime.Decode
import TrafficSpec.Core.Vocab.Intentions
open TrafficSpec
private def readData {α : Type} (decoder : Lean.Json → Decode.D α) (path : String) : IO α := do
  let text ← IO.FS.readFile path
  match Decode.parse decoder text with
  | .ok value => pure value
  | .error message => throw (IO.userError message)
def main (args : List String) : IO UInt32 := do
  try
    let (tracePath, manifestPath, intentionsOnly) ← match args with
      | [t, m] => pure (t, m, false)
      | [t, m, "--intentions-only"] => pure (t, m, true)
      | _ => throw (IO.userError "expected trace and manifest, optionally --intentions-only")
    let trace ← readData Decode.trace tracePath
    let manifest ← readData Decode.manifest manifestPath
    if !intentionsOnly && !manifest.complete then throw (IO.userError "manifest is not complete")
    let mut intentCount := 0
    let mut sourceClassCount := 0
    for scene in trace do
      let tracks := scene.users.map (·.track)
      let regions := scene.structures.map (·.id)
      let devices := scene.devices.map (·.id)
      let trackSet := Std.HashSet.ofList tracks
      let regionSet := Std.HashSet.ofList regions
      let deviceSet := Std.HashSet.ofList devices
      let regionKinds := Std.HashMap.ofList (scene.structures.map fun st => (st.id, st.kind))
      if tracks.length != trackSet.size || regions.length != regionSet.size || devices.length != deviceSet.size then
        throw (IO.userError "duplicate entity identity")
      if !(scene.subject.map trackSet.contains).getD false then throw (IO.userError "subject not in users")
      if !(scene.occupies.all fun (t, r) => trackSet.contains t && regionSet.contains r) then throw (IO.userError "dangling occupancy")
      if !(scene.devices.all fun d => d.governs.all regionSet.contains) then throw (IO.userError "dangling device governs")
      for u in scene.users do
        if u.sourceClassifications.isSome then sourceClassCount := sourceClassCount + 1
      for reference in scene.references do
        let present := match reference.kind with
          | .track => trackSet.contains reference.id
          | .region => regionSet.contains reference.id
          | .device => deviceSet.contains reference.id
        if !present then throw (IO.userError s!"dangling reference: {reference.place}")
        if let some kind := reference.structureKind then
          if !((regionKinds.get? reference.id).map fun actual => structureRefines actual kind).getD false then
            throw (IO.userError s!"wrong reference kind: {reference.place}")
      for st in scene.structures do
        if let some lanes := st.entranceOf then
          if st.kind != .stopLine && st.kind != .crosswalk then
            throw (IO.userError "entrance_of on unsupported region")
          if lanes.length != lanes.eraseDups.length then
            throw (IO.userError "duplicate entrance_of target")
      let pairs := scene.intents.map fun d => (d.vehicle, d.target)
      if pairs.length != pairs.eraseDups.length then throw (IO.userError "duplicate intent vehicle/target")
      for d in scene.intents do
        if !trackSet.contains d.vehicle || !regionSet.contains d.target then throw (IO.userError "dangling intent reference")
        let ids := d.values.map (·.1)
        if ids.length != ids.eraseDups.length then throw (IO.userError "duplicate intention id")
        if !(ids.all IntId.wellFormed) then throw (IO.userError "malformed intention id")
        intentCount := intentCount + 1
    IO.println s!"decoded_frames={trace.length}; decoded_intents={intentCount}; source_classifications={sourceClassCount}; source_capabilities={manifest.sourceEntries.length}; manifest_complete={manifest.complete}; full_core=true; intentions_only={intentionsOnly}"
    return (0 : UInt32)
  catch error =>
    IO.eprintln error
    return (2 : UInt32)
'''


def build_validator(library, workspace, lake):
    library,workspace,lake=map(lambda p:Path(p).resolve(),(library,workspace,lake))
    from intentions import core_contract
    contract=core_contract(library)
    workspace.mkdir(parents=True,exist_ok=False)
    # Copy only Core .lean source. Overlay the actual full-split files on the
    # common modules; never activate a split in the supplied repository.
    for p in (library/'TrafficSpec/Core').rglob('*.lean'):
        target=workspace/'TrafficSpec/Core'/p.relative_to(library/'TrafficSpec/Core')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    core=full_core(library)
    for p in core.rglob('*.lean'):
        target=workspace/'TrafficSpec/Core'/p.relative_to(core)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    (workspace/'lean-toolchain').write_text((library/'lean-toolchain').read_text())
    (workspace/'lakefile.lean').write_text('import Lake\nopen Lake DSL\npackage adapterCheck\nlean_lib TrafficSpec\nlean_exe adapterCheck where\n  root := `AdapterCheck\n')
    (workspace/'AdapterCheck.lean').write_text(VALIDATOR)
    env=dict(os.environ,ELAN_HOME=str(lake.parent.parent))
    with (workspace/'build.log').open('w') as log:
        result=subprocess.run([str(lake),'build','adapterCheck'],cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('Full decoder build failed; see '+str(workspace/'build.log'))
    if core_contract(library)!=contract:raise RuntimeError('Core contract changed during isolated build')
    contract['validator_source_sha256']=__import__('hashlib').sha256(VALIDATOR.encode()).hexdigest()
    contract['validator_sha256']=__import__('hashlib').sha256((workspace/'.lake/build/bin/adapterCheck').read_bytes()).hexdigest()
    (workspace/'intention-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    return workspace/'.lake/build/bin/adapterCheck'


def validate_output(output, validator):
    output=Path(output).resolve()
    from intentions import validate_scene_intents
    from trace_json import scenes
    expected_intents=sum(len(validate_scene_intents(scene)) for scene,_ in scenes(output/'trace.json'))
    result=subprocess.run([str(Path(validator).resolve()),str(output/'trace.json'),str(output/'manifest.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    (output/'decoder.stdout.log').write_text(result.stdout)
    (output/'decoder.stderr.log').write_text(result.stderr)
    report=json.loads((output/'adapter_report.json').read_text())
    report['decoder_validation']={'passed':result.returncode==0,'exit_code':result.returncode,'executable':str(Path(validator).resolve()),'output':result.stdout.strip(),'scope':'full Core decoding and entity references; no law evaluation'}
    (output/'adapter_report.json').write_text(json.dumps(report,indent=2)+'\n')
    if result.returncode:raise RuntimeError('TrafficSpec decoder rejected output: '+result.stderr.strip())
    if expected_intents and ('decoded_intents='+str(expected_intents)+';') not in result.stdout:
        report['decoder_validation']['passed']=False
        (output/'adapter_report.json').write_text(json.dumps(report,indent=2)+'\n')
        raise RuntimeError('Decoder did not confirm typed intention count; rebuild with current Core')
    return report


def validate_saved_intentions(trace, manifest_path, validator, output, *, batch_frames=20):
    """Validate all original declarations using exact-ID intent-only views.

    Historical class/geometry codecs can differ from current Core. These views
    do not replace recordings or claim validation of unrelated ontology fields.
    """
    from intentions import validate_scene_intents
    from trace_json import scenes
    import hashlib
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    frames=0;intent_count=0;previous=None;batch=[];checks=[];digest=hashlib.sha256()
    def flush():
        if not batch:return
        path=output/('batch-%05d.json'%len(checks));path.write_text(json.dumps({'scenes':batch},separators=(',',':')))
        expected=sum(len(s['intents']) for s in batch)
        result=subprocess.run([str(validator),str(path),str(manifest_path),'--intentions-only'],capture_output=True,text=True)
        (path.with_suffix('.stdout.log')).write_text(result.stdout)
        (path.with_suffix('.stderr.log')).write_text(result.stderr)
        if result.returncode or ('decoded_intents='+str(expected)+';') not in result.stdout:
            raise RuntimeError('Authoritative intention-view validation failed: '+result.stderr.strip()+' '+result.stdout.strip())
        checks.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                       'frames':len(batch),'intents':expected,'first_t':batch[0]['t'],'last_t':batch[-1]['t'],
                       'decoder_stdout':result.stdout.strip()})
        batch.clear()
    for scene,_ in scenes(trace):
        records=validate_scene_intents(scene)
        if previous is not None and scene['t']<=previous:raise ValueError('Nonmonotone original scene times')
        previous=scene['t'];targets={d['target'] for d in records}
        view={'t':scene['t'],'subject':scene.get('subject'),
              'users':[{'track':u['track']} for u in scene['users']],
              'structures':[{'id':r['id'],'kind':r['kind']} for r in scene['structures'] if r['id'] in targets],
              'intents':records}
        if view['subject'] not in {u['track'] for u in view['users']}:raise ValueError('Dangling original subject')
        digest.update(json.dumps(view,separators=(',',':')).encode());batch.append(view)
        frames+=1;intent_count+=len(records)
        if len(batch)>=batch_frames:flush()
    flush()
    if not frames:raise ValueError('Empty intention validation trace')
    report={'passed':True,'scope':'intention declarations and their original times/entity bindings only; not full historical ontology or statutory evaluation',
            'frames':frames,'intent_records':intent_count,'view_digest':digest.hexdigest(),'batches':checks,
            'validator':str(validator),'validator_sha256':hashlib.sha256(Path(validator).read_bytes()).hexdigest()}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
