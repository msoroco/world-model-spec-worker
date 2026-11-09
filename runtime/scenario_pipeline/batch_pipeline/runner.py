"""Bounded asynchronous semantic workers with durable retries and leases."""
import asyncio
import json
import os
import random
import signal
import threading
import time
import uuid
from contextlib import asynccontextmanager
from . import stages


class AdapterError(Exception):
    def __init__(self, message, transient=False, metadata=None):
        super().__init__(message)
        self.transient = transient
        self.metadata = metadata or {}


class AccountUsageLimitError(AdapterError):
    """An account-wide limit that must stop dispatch across the whole run."""


class CommandAdapter:
    """A model bridge reads one JSON request on stdin and emits one JSON response.

    Response: {"result": {...}, "metadata": {"model": ..., "usage": ...}}.
    External bridges may call any API/SDK; no credentials are stored in SQLite.
    """
    def __init__(self, command, timeout=300):
        self.command = command
        self.timeout = timeout

    async def call(self, request):
        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(*self.command, stdin=asyncio.subprocess.PIPE,
                         stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
        try:
            out, err = await asyncio.wait_for(process.communicate(json.dumps(request).encode()), self.timeout)
        except asyncio.TimeoutError:
            os.killpg(process.pid,signal.SIGKILL); await process.wait()
            raise AdapterError('Model worker timeout', True)
        except BaseException:
            os.killpg(process.pid,signal.SIGKILL); await process.wait(); raise
        if process.returncode:
            combined = (err+b'\n'+out).decode(errors='replace')
            msg = combined[-4000:]
            folded = combined.casefold()
            if 'usage limit' in folded and ('try again at' in folded or 'purchase more credits' in folded):
                raise AccountUsageLimitError('Model account usage limit reached: '+msg, False,
                    {'elapsed_s':time.monotonic()-start,'account_limit':True})
            transient = process.returncode in (75, 429) or any(x in msg.lower() for x in ('rate limit','429','503','temporarily unavailable','selected model is at capacity'))
            raise AdapterError('Model worker failed: '+msg, transient, {'elapsed_s':time.monotonic()-start})
        try:
            response = json.loads(out)
        except (ValueError, UnicodeError) as exc:
            raise AdapterError('Invalid worker JSON: '+str(exc), False, {'raw_output':out.decode(errors='replace')[-8000:]})
        if 'error' in response:
            raise AdapterError(str(response['error']), bool(response.get('retryable')), response.get('metadata'))
        return response.get('result', response), dict(response.get('metadata', {}), elapsed_s=time.monotonic()-start,
                    adapter='command', command=self.command)


class RateLimiter:
    def __init__(self, per_minute, max_concurrency=None):
        self.interval = 60/per_minute if per_minute else 0
        self.next = 0
        # The production coordinator can run planning and construction on
        # separate event loops in the same process. Reserve each start slot
        # under a thread lock so both loops still share one global limiter.
        self.lock = threading.Lock()
        if max_concurrency is not None and max_concurrency < 1:
            raise ValueError('Model concurrency must be positive')
        self.max_concurrency = max_concurrency
        self.active_requests = 0
        self.request_waiters = []

    def configure_concurrency(self, maximum):
        if maximum < 1:
            raise ValueError('Model concurrency must be positive')
        with self.lock:
            if self.max_concurrency == maximum:
                return
            if self.active_requests or self.request_waiters:
                raise ValueError('Cannot change concurrency beneath active requests')
            self.max_concurrency = maximum

    @asynccontextmanager
    async def request_slot(self):
        if self.max_concurrency is None:
            yield
            return
        ticket = object()
        acquired = False
        with self.lock:
            self.request_waiters.append(ticket)
        try:
            while not acquired:
                with self.lock:
                    if self.request_waiters[0] is ticket and self.active_requests < self.max_concurrency:
                        self.request_waiters.pop(0)
                        self.active_requests += 1
                        acquired = True
                if not acquired:
                    await asyncio.sleep(.05)
            yield
        finally:
            with self.lock:
                if acquired:
                    self.active_requests -= 1
                elif ticket in self.request_waiters:
                    self.request_waiters.remove(ticket)

    async def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = max(0, self.next-now)
            self.next = max(now,self.next)+self.interval
        if delay:
            await asyncio.sleep(delay)


@asynccontextmanager
async def _request_slot(limiter):
    gate = getattr(limiter, 'request_slot', None)
    if gate is None:
        yield
    else:
        async with gate():
            yield


async def run(store, run_id, command, concurrency=4, per_minute=30, max_attempts=3, timeout=300, stage_names=None, job_ids=(), limiter=None):
    if not command:
        raise ValueError('Configure --worker as a JSON argv array; no paid model calls are made implicitly.')
    owner = uuid.uuid4().hex
    adapter = CommandAdapter(command, timeout)
    limiter = limiter or RateLimiter(per_minute)
    selected = stage_names or stages.SEMANTIC_STAGES
    job_ids=tuple(job_ids)
    job_filter=(' AND j.id IN ('+','.join('?' for _ in job_ids)+')') if job_ids else ''
    writer = asyncio.Lock()
    handled = 0
    construction_locks = {}
    halt_dispatch = asyncio.Event()

    async def worker():
        nonlocal handled
        while not halt_dispatch.is_set():
            job = store.claim(run_id, owner, selected, max(180,timeout+60),job_ids=job_ids)
            if job is None:
                running = store.db.execute("SELECT COUNT(*) FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.status='running' AND j.owner=?",(run_id,owner)).fetchone()[0]
                retry = store.db.execute("SELECT MIN(j.available) FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.status='pending' AND j.available>? AND j.stage IN (%s)" % ','.join('?' for _ in selected)+job_filter+" AND NOT EXISTS (SELECT 1 FROM dependencies d JOIN jobs p ON p.id=d.dependency_id WHERE d.job_id=j.id AND p.status!='completed')",(run_id,time.time(),*selected,*job_ids)).fetchone()[0]
                if running or retry is not None:
                    await asyncio.sleep(min(1,max(.05,(retry-time.time()) if retry else .2)))
                    continue
                return
            async def heartbeat():
                while True:
                    await asyncio.sleep(20)
                    store.heartbeat(job['id'],owner,max(180,timeout+60))
            pulse = asyncio.create_task(heartbeat())
            metadata = {}
            construction_lock = None
            construction_lock_acquired = False
            try:
                if job['stage'] == 'construction':
                    from .construction_reuse import group_key
                    key = group_key(json.loads(job['payload'])) or (job['id'],)
                    construction_lock = construction_locks.setdefault(key, asyncio.Lock())
                    await construction_lock.acquire()
                    construction_lock_acquired = True
                inputs, provenance = stages.input_context(store,run_id,job)
                if job.get('error'):
                    inputs['previous_attempt_error'] = job['error']
                attach_previous_response(inputs,job,stages.run_info(store,run_id)['output'])
                reusable = None
                if job['stage'] == 'construction':
                    from .construction_reuse import instantiate
                    reusable = instantiate(inputs)
                if reusable is not None:
                    result, metadata = reusable, {'adapter': 'configuration_reuse', 'elapsed_s': 0, 'new_model_call': False}
                elif job['stage']=='relevance':
                    result={'cell_id':inputs['request']['cell']['cell_id'],'actor':job['actor'],'status':'draft',
                            'relevant_laws':[l for d in inputs['dependencies'] for l in d['relevant_laws']],
                            'borderline_excluded':[l for d in inputs['dependencies'] for l in d['borderline_excluded']]}
                    metadata={'adapter':'deterministic_merge','elapsed_s':0}
                else:
                    async with _request_slot(limiter):
                        await limiter.wait()
                        if halt_dispatch.is_set():
                            store.fail(job,owner,'Stopped after an account-wide model usage limit',retry=True,metadata=metadata)
                            return
                        request = stages.prompt(job['stage'], inputs)
                        request['_worker_evidence_directory'] = str(__import__('pathlib').Path(
                            stages.run_info(store, run_id)['output'])/'logs/workers'/str(job['id'])/
                            ('attempt-'+str(job['attempts'])))
                        if job['stage']=='construction':
                            from .runtime_dependencies import execution_guard
                            with execution_guard(store,run_id):
                                result, metadata = await adapter.call(request)
                        else:
                            result, metadata = await adapter.call(request)
                    from pathlib import Path
                    from .store import atomic
                    evidence = Path(request['_worker_evidence_directory'])
                    evidence.mkdir(parents=True, exist_ok=True)
                    atomic(evidence/'candidate.json', result)
                if job['stage'] == 'cases':
                    from .sweeps import expand_sweeps
                    binding = next((d for d in inputs['dependencies'] if 'variable_parameters' in d), None)
                    expand_sweeps(result, inputs.get('templates', []), binding)
                if job['stage'] == 'construction':
                    from .construction_contract import normalize_entrypoint
                    normalize_entrypoint(result)
                stages.validate(job['stage'],result,inputs)
                if job['stage'] == 'template':
                    result['source_required_observations'] = inputs['law_summary'].get('required_observations', [])
                    result['source_residue'] = inputs['law_summary'].get('residue', [])
                async with writer:
                    store.finish(job,owner,result,provenance,metadata,
                        lambda aid: stages.expand(store,run_id,job,result,aid) if store.db.execute('SELECT active FROM run_jobs WHERE run_id=? AND job_id=?', (run_id, job['id'])).fetchone()[0] else None)
                    if job['stage'] in ('relevance', 'template', 'judgment_observables'):
                        materialize_cached(store, run_id)
                handled += 1
                print(json.dumps({'job_id':job['id'],'stage':job['stage'],'entity':job['entity'],'status':'completed'}),flush=True)
            except AccountUsageLimitError as exc:
                halt_dispatch.set()
                store.fail(job,owner,exc,retry=False,metadata=exc.metadata)
                raise
            except asyncio.CancelledError:
                store.fail(job,owner,'Interrupted; attempt retained',retry=True,metadata=metadata)
                raise
            except Exception as exc:
                contract_error = isinstance(exc, ValueError) and not str(exc).startswith(('Missing pre-extracted', 'Construction not executable:', 'Template regeneration would erase', 'Conflicting observable'))
                transient = isinstance(exc,AdapterError) and exc.transient or contract_error
                retry = transient and job['attempts'] < max_attempts
                delay = min(60,2**job['attempts']) * random.uniform(.75,1.25) if retry else 0
                blocked = isinstance(exc,ValueError) and str(exc).startswith(('Missing pre-extracted','Construction not executable:'))
                store.fail(job,owner,exc,retry,delay,blocked,metadata if not isinstance(exc,AdapterError) else exc.metadata)
                print(json.dumps({'job_id':job['id'],'stage':job['stage'],'status':'pending' if retry else 'blocked' if blocked else 'failed','error':str(exc)}),flush=True)
            finally:
                if construction_lock_acquired:
                    construction_lock.release()
                pulse.cancel()
                await asyncio.gather(pulse,return_exceptions=True)
    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    try:
        await asyncio.gather(*workers)
    except BaseException:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers,return_exceptions=True)
        raise
    return handled


def materialize_cached(store, run_id):
    """Expand cached successful jobs without calling a model or rerunning CARLA."""
    while True:
        before = store.db.execute('SELECT COUNT(*) FROM run_jobs WHERE run_id=?',(run_id,)).fetchone()[0]
        jobs = store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.status='completed'",(run_id,)).fetchall()
        with store.transaction():
            for row in jobs:
                if not store.db.execute('SELECT active FROM run_jobs WHERE run_id=? AND job_id=?', (run_id, row['id'])).fetchone()[0]:
                    continue
                if row['stage'] in ('relevance','bindings'):
                    result = store.artifact(row['artifact_id'])['payload']
                    stages.expand(store,run_id,dict(row),result,row['artifact_id'])
        after = store.db.execute('SELECT COUNT(*) FROM run_jobs WHERE run_id=?',(run_id,)).fetchone()[0]
        if before == after:
            break


def attach_previous_response(inputs, job, output):
    """Supply only a same-job retained response, bound to the unchanged request."""
    if job['stage'] not in ('cases','construction') or not job.get('error') or job['attempts']<2:
        return
    from pathlib import Path
    import hashlib
    directory=Path(output)/'logs/workers'/str(job['id'])/('attempt-'+str(job['attempts']-1))
    response=directory/'response.json';request=directory/'complete_request.json'
    if not response.is_file() or not request.is_file():
        return
    try:
        prior=json.loads(request.read_text())
        if prior['inputs']['request']!=json.loads(job['payload']):
            return
        raw=response.read_bytes();result=json.loads(raw)
    except (ValueError,KeyError,TypeError):
        return
    inputs['previous_attempt_result']={'job_id':job['id'],'attempt':job['attempts']-1,
        'sha256':hashlib.sha256(raw).hexdigest(),'result':result,
        'instructions':'Retained diagnostic evidence from this same unchanged request. Diagnose the actual failure; preserve every current frozen requirement and all unknowns. This response is not executable or accepted merely because it exists. Do not repeat unchanged code or copy unsupported claims as facts.'}
