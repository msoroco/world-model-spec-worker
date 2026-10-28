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

VALIDATOR = '''import TrafficSpec.Core.Runtime.Decode
open TrafficSpec
private def readData {α : Type} (decoder : Lean.Json → Decode.D α) (path : String) : IO α := do
  let text ← IO.FS.readFile path
  match Decode.parse decoder text with
  | .ok value => pure value
  | .error message => throw (IO.userError message)
def main (args : List String) : IO UInt32 := do
  try
    let [tracePath, manifestPath] := args | throw (IO.userError "expected trace and manifest")
    let trace ← readData Decode.trace tracePath
    let manifest ← readData Decode.manifest manifestPath
    if !manifest.complete then throw (IO.userError "manifest is not complete")
    for scene in trace do
      let tracks := scene.users.map (·.track)
      let regions := scene.structures.map (·.id)
      let devices := scene.devices.map (·.id)
      if tracks.length != tracks.eraseDups.length || regions.length != regions.eraseDups.length || devices.length != devices.eraseDups.length then
        throw (IO.userError "duplicate entity identity")
      if !(scene.subject.map tracks.contains).getD false then throw (IO.userError "subject not in users")
      if !(scene.occupies.all fun (t, r) => tracks.contains t && regions.contains r) then throw (IO.userError "dangling occupancy")
      if !(scene.devices.all fun d => d.governs.all regions.contains) then throw (IO.userError "dangling device governs")
    IO.println s!"decoded_frames={trace.length}; manifest_complete=true; full_core=true"
    return (0 : UInt32)
  catch error =>
    IO.eprintln error
    return (2 : UInt32)
'''


def build_validator(library, workspace, lake):
    library,workspace,lake=map(lambda p:Path(p).resolve(),(library,workspace,lake))
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
    return workspace/'.lake/build/bin/adapterCheck'


def validate_output(output, validator):
    output=Path(output).resolve()
    result=subprocess.run([str(Path(validator).resolve()),str(output/'trace.json'),str(output/'manifest.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    (output/'decoder.stdout.log').write_text(result.stdout)
    (output/'decoder.stderr.log').write_text(result.stderr)
    report=json.loads((output/'adapter_report.json').read_text())
    report['decoder_validation']={'passed':result.returncode==0,'exit_code':result.returncode,'executable':str(Path(validator).resolve()),'output':result.stdout.strip(),'scope':'full Core decoding and entity references; no law evaluation'}
    (output/'adapter_report.json').write_text(json.dumps(report,indent=2)+'\n')
    if result.returncode:raise RuntimeError('TrafficSpec decoder rejected output: '+result.stderr.strip())
    return report
