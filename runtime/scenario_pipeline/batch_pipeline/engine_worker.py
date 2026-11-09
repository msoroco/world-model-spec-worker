"""One local/SSH execution process. Never opens SQLite or schedules work."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_pipeline.completion import atomic_result, seal, sha


def verify_runtime(binding):
    for filename, expected in binding['runtime_dependency_hashes'].items():
        path = Path(filename)
        if not path.is_file() or sha(path) != expected:
            raise ValueError('Runtime dependency changed: ' + filename)


def server_identity(port):
    """Identify the actual listening process, independently of hostname aliases."""
    inodes = set()
    for table in ('/proc/net/tcp', '/proc/net/tcp6'):
        for line in Path(table).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A' and int(fields[1].split(':')[1], 16) == port:
                inodes.add(fields[9])
    pids = set()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            for fd in (entry / 'fd').iterdir():
                try:
                    if os.readlink(str(fd)) in {'socket:[' + i + ']' for i in inodes}:
                        pids.add(int(entry.name))
                except OSError:
                    pass
        except OSError:
            pass
    if len(pids) != 1:
        raise ValueError('Cannot establish one owned listening CARLA process on port ' + str(port))
    pid = pids.pop()
    proc = Path('/proc') / str(pid)
    if 'carla' not in (proc / 'comm').read_text().lower():
        raise ValueError('Listening process is not CARLA')
    return {'node': socket.gethostname(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'pid': pid, 'start_ticks': (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]}


def identity_key(identity):
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def probe(port, allow_login_node=False):
    identity = server_identity(port)
    if socket.gethostname().startswith('login') and not allow_login_node:
        raise ValueError('Sustained simulation requires user-provided compute resources, not a login node')
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,memory.total,memory.free,utilization.gpu',
                                   '--format=csv,noheader'], universal_newlines=True, timeout=10)
    return {'server_identity': identity, 'gpu_snapshot': gpu.strip(),
            'host_memory': Path('/proc/meminfo').read_text(), 'cpu_load': os.getloadavg(),
            'slurm_job_id': os.environ.get('SLURM_JOB_ID'),
            'allow_login_node': allow_login_node,
            'resource_note': 'Snapshot only. Engines must already be dedicated and allocated by the user.'}


def run_attempt(request):
    directory = Path(request['directory'])
    identity = server_identity(request['port'])
    if identity != request['binding']['server_identity']:
        raise ValueError('CARLA process changed after preflight')
    lock = Path(request['lock_directory']) / (identity_key(identity) + '.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    phase = 'static'
    recording_closed = False
    child = None
    stage = None
    execution_directory = directory
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            verify_runtime(request['binding'])
            if request.get('scratch_fallback'):
                from batch_pipeline.staging import Stage, cleanup
                cleanup(request['scratch_fallback']['root'])
                stage=Stage(directory,request['scratch_fallback'])
                execution_directory=stage.directory
            next_cleanup=time.monotonic()+3600
            env = dict(os.environ, **request['env'])
            command = [sys.executable, str(execution_directory / request['entrypoint'])]
            for phase, args in [('static', ['--check']), ('recorded', ['--output-dir', str(execution_directory),
                                     '--host', request['host'], '--port', str(request['port'])])]:
                with (execution_directory / (phase + '.stdout.log')).open('w') as out, (execution_directory / (phase + '.stderr.log')).open('w') as err:
                    # Keep exclusivity if the worker dies while its runner survives.
                    child = subprocess.Popen(command + args, cwd=str(execution_directory), env=env, stdout=out, stderr=err,
                                             start_new_session=True, pass_fds=(stream.fileno(),))
                    phase_timeout=request.get('static_timeout',request['timeout']) if phase=='static' else request['timeout']
                    deadline=time.monotonic()+phase_timeout
                    while True:
                        if stage:
                            stage.check_capacity()
                            if time.monotonic()>=next_cleanup:
                                cleanup(request['scratch_fallback']['root']);next_cleanup=time.monotonic()+3600
                        remaining=deadline-time.monotonic()
                        if remaining<=0:raise subprocess.TimeoutExpired(command,phase_timeout)
                        try:
                            code=child.wait(timeout=min(2,remaining));break
                        except subprocess.TimeoutExpired:pass
                if code and (phase == 'static' or not (execution_directory / 'result.json').is_file()):
                    raise RuntimeError(phase + ' runner failed: ' + str(code))
                if phase == 'recorded':
                    result = json.loads((execution_directory / 'result.json').read_text())
                    result['recorded_exit_code'] = code
                    atomic_result(execution_directory / 'result.json', result)
            if server_identity(request['port']) != identity:
                raise ValueError('CARLA process changed during execution')
            verify_runtime(request['binding'])
            if stage:stage.publish()
            # Child wait, server identity, runtime verification and publication succeeded.
            recording_closed = True
            seal(directory, request['binding'])
            if stage:stage.cleanup()
        except BaseException as exc:
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
            if stage:
                try:
                    stage.publish();stage.cleanup()
                except (OSError,ValueError,RuntimeError):
                    pass  # Registered untransferred evidence must remain retained.
            atomic_result(directory / 'failure.json', {'error': str(exc), 'phase': phase,
                         'engine_unavailable': phase == 'recorded' and not recording_closed,
                         'termination_confirmed': recording_closed, 'binding': request['binding']})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=int)
    parser.add_argument('--allow-login-node', action='store_true', help='Explicit user authorization for this dedicated engine')
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.probe is not None:
        print(json.dumps(probe(args.probe, args.allow_login_node)))
    elif args.request is not None:
        def interrupted(signum, frame):
            raise InterruptedError('Worker interrupted by signal ' + str(signum))
        signal.signal(signal.SIGTERM, interrupted)
        run_attempt(json.loads(args.request.read_text()))
    else:
        parser.error('Specify --probe or --request')


if __name__ == '__main__':
    main()
