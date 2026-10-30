"""Proposed capture-exit repair text for lead integration; never modifies shared files."""
import difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD="""    subprocess.run([python,str(entry),'--output-dir',str(destination),'--host',host,'--port',str(port)],cwd=destination,env=env,check=True)
    from .saved_processing import record_native_exit
    record_native_exit(destination)
"""
NEW="""    from .saved_processing import record_native_exit
    try:
        subprocess.run([python,str(entry),'--output-dir',str(destination),'--host',host,'--port',str(port)],cwd=destination,env=env,check=True)
    except subprocess.CalledProcessError as native_failure:
        try:
            receipt=record_native_exit(destination)
            receipt.update(native_process_exit_code=native_failure.returncode,capture_command_failed=True)
            write(destination/'native-exit.json',receipt)
        except Exception as closure_error:
            # Never replace the original Native command failure with a receipt error.
            try:write(destination/'native-exit-feedback.json',{'recorded_only':True,'native_process_exit_code':native_failure.returncode,'error':str(closure_error),'native_replay_requested':False})
            except Exception:pass
        raise
    receipt=record_native_exit(destination)
    receipt.update(native_process_exit_code=0,capture_command_failed=False)
    write(destination/'native-exit.json',receipt)
"""
def proposed(source):
 if NEW in source:return source
 if source.count(OLD)!=1:raise ValueError('Unexpected capture exit source; review before applying')
 return source.replace(OLD,NEW)
if __name__=='__main__':
 path=ROOT/'work/_shared/runtime-overlay/scenario_pipeline/worker_exchange/runtime_cli.py'
 source=path.read_text();diff=''.join(difflib.unified_diff(source.splitlines(True),proposed(source).splitlines(True),fromfile=str(path.relative_to(ROOT)),tofile=str(path.relative_to(ROOT))))
 Path(__file__).with_suffix('.diff').write_text(diff)
 print(diff)
