"""Rebuild and verify the current C132497 text-only CPU request package."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
NATIVE=ROOT/'native'
PYTHON=sys.executable
COMMANDS=(NATIVE/'propose_ccw.py',NATIVE/'build.py',NATIVE/'audit_ccw_design.py',
          NATIVE/'build_saved.py',ROOT/'build_offline.py',
          NATIVE/'prove_camera_calls.py',NATIVE/'prove_capture_output.py',
          NATIVE/'prove_roundabout_topology.py',
          NATIVE/'audit_construction.py',ROOT/'prove_compatibility.py',
          NATIVE/'audit_saved.py',NATIVE/'prove_comparison.py',
          NATIVE/'prove_triggers.py',NATIVE/'audit_triggers.py',
          NATIVE/'audit_comparison.py',NATIVE/'build_statutory.py',NATIVE/'audit_statutory.py',
          ROOT/'audit_package.py')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


log=[]
for script in COMMANDS:
    result=subprocess.run([PYTHON,str(script)],capture_output=True,text=True)
    log.append({'script':str(script.relative_to(ROOT)),'exit_code':result.returncode,
                'output':result.stdout+result.stderr})
    if result.returncode:
        (ROOT/'update015-right-exit-repair-command.log').write_text(
            ''.join(f"{row['script']}: {row['exit_code']}\n{row['output']}" for row in log))
        raise ValueError('Current right-exit CPU proof failed: '+str(script))

names=('overview','approach','reference_corner','driver_reference')
sizes=([1920,1080],[1280,720],[1280,720],[1280,720])
camera_checks=[]
for witness in ('reference','contrast'):
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        bundle=ROOT/'offline/bundles'/witness/candidate
        result=subprocess.run([PYTHON,str(bundle/'capture.py'),'--bundle',str(bundle),'--check'],
                              capture_output=True,text=True)
        if result.returncode:
            raise ValueError('Four-camera capture check failed: '+result.stderr)
        value=json.loads(result.stdout)
        if (tuple(value['camera_names'])!=names or value['camera_dimensions']!=list(sizes) or
                set(value['requested_phases'])!={'entry','circulation','exit'} or
                value['original_native_observed'] is not False):
            raise ValueError('Capture plan lacks exact full exit or four cameras')
        if value['camera_positions_m'][0][2]!=(42 if candidate=='fallback2' else 35):
            raise ValueError('Elevation fallback does not change overview geometry')
        track=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
        if candidate=='fallback3' and (any(row['ego_speed_mps']!=0 for row in track[:40]) or
                                       track[40]['ego_speed_mps']<=0):
            raise ValueError('Dwell candidate does not execute distinct controller policy')
        camera_checks.append({'case_id':value['case_id'],'candidate_id':candidate,
                              'phases':value['requested_phases'],
                              'camera_dimensions':value['camera_dimensions'],
                              'capture_sha256':sha(bundle/'capture.py')})

log_path=ROOT/'update015-right-exit-repair-command.log'
log_path.write_text(''.join(f"{row['script']}: {row['exit_code']}\n{row['output']}" for row in log))
proof={'format':'c132497-current-request-repair-proof-v1','passed':True,
       'assignment_id':ROOT.name,'copied_bundles':8,'authored_exit_requests':8,
       'closed_loop_xml_geometry_authored':True,
       'counterclockwise_source_context_passed':True,
       'camera_checks':camera_checks,'source_positive_checks':8,
       'source_negative_rejections':40,'raw_saved_positive_checks':24,
       'raw_saved_negative_rejections':40,'synthetic_comparison_pairs':4,
       'original_native_observed':False,'current_runtime_offline_passed':False,
       'current_runtime_compatibility_passed':False,'current_runtime_process_saved_passed':False,
       'delivery_ready':False,'command_log':'update015-right-exit-repair-command.log',
       'command_log_sha256':sha(log_path),
       'construction_manifest_sha256':sha(NATIVE/'manifest.json'),
       'copied_manifest_sha256':sha(ROOT/'offline/manifest.json'),
       'compatibility_proof_sha256':sha(ROOT/'offline/proof-compatibility.json'),
       'comparison_audit_sha256':sha(ROOT/'offline/audit-comparison.json')}
output=ROOT/'update015-right-exit-repair-proof.json'
output.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'passed':True,'bundles':8,'exit_requests':8,
                  'sha256':sha(output)}))
