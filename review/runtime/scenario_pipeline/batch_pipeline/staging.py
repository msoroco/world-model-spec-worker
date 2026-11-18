"""Diagnosed filesystem fallback, owned staging and verified durable cleanup.

Default execution is persistent scratch. Never delete untransferred evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import time
from .completion import atomic_result, sha


def memory_headroom():
    """Host available memory bounded by the controller's cgroup allowance."""
    values={line.split(':')[0]:int(line.split()[1])*1024
            for line in Path('/proc/meminfo').read_text().splitlines()if line.startswith('MemAvailable:')}
    bounds=[values['MemAvailable']]
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        hierarchy,controllers,path=line.split(':',2)
        if hierarchy=='0' and not controllers:
            current=Path('/sys/fs/cgroup')/path.lstrip('/')
            while current==Path('/sys/fs/cgroup')or Path('/sys/fs/cgroup')in current.parents:
                limit=current/'memory.max';used=current/'memory.current'
                if limit.exists()and used.exists()and limit.read_text().strip()!='max':
                    bounds.append(max(0,int(limit.read_text())-int(used.read_text())))
                if current==Path('/sys/fs/cgroup'):break
                current=current.parent
    return min(bounds)


def is_tmpfs(path):
    """Use the containing mount, without shell interpolation or broad traversal."""
    matches=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);mount=Path(left.split()[4].replace('\\040',' '))
        if path==mount or mount in path.parents:matches.append((len(mount.parts),right.split()[0]))
    return bool(matches)and max(matches)[1]=='tmpfs'


class Stage:
    def __init__(self, destination, policy):
        self.destination=Path(destination).resolve();self.policy=policy
        if not policy.get('diagnosis') or not policy.get('root'):
            raise ValueError('Staging requires an explicit filesystem diagnosis and root')
        self.root=Path(policy['root']).resolve()
        if self.root==Path('/') or self.root==Path('/tmp'):
            raise ValueError('Use a task-owned staging subtree, not a shared root')
        self.root.mkdir(parents=True,exist_ok=True)
        if self.root.stat().st_uid!=os.getuid():raise ValueError('Staging root is not owned by this user')
        self.maximum=int(policy.get('max_bytes',8*1024**3))
        free=shutil.disk_usage(self.root).free
        self.tmpfs=is_tmpfs(self.root)
        if self.maximum<=0 or free < self.maximum:
            raise ValueError('Insufficient staging capacity; do not dispatch')
        if self.tmpfs and memory_headroom()<self.maximum+512*1024**2:
            raise ValueError('Insufficient effective memory for tmpfs staging; do not dispatch')
        self.directory=Path(tempfile.mkdtemp(prefix='attempt-',dir=str(self.root)))
        # No source paths or other-user trees are cleaned by this registry.
        self.owner={'node':socket.gethostname(),'uid':os.getuid(),'pid':os.getpid(),
                    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]}
        self.receipt={'format':'owned-capture-stage-v1','directory':str(self.directory),
            'destination':str(self.destination),'owner':self.owner,'created_at':time.time(),
            'diagnosis':policy['diagnosis'],'maximum_bytes':self.maximum,'state':'active'}
        self.registry=self.root/(self.directory.name+'.json')
        atomic_result(self.registry,self.receipt)
        for p in self.destination.rglob('*'):
            if p.is_symlink():raise ValueError('Frozen staged inputs cannot be symlinks')
            if p.is_file() and p.name not in ('result.json','failure.json','worker.stdout.log','worker.stderr.log','worker_request.json'):
                target=self.directory/p.relative_to(self.destination);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(p,target)

    def check_capacity(self):
        size=sum(p.stat().st_size for p in self.directory.rglob('*') if p.is_file())
        if size>self.maximum:raise RuntimeError('Owned staging budget exceeded; retain evidence')
        if self.tmpfs and memory_headroom()<256*1024**2:
            raise RuntimeError('Effective tmpfs memory exhausted; stop and retain evidence')
        return size

    def publish(self):
        """Copy closed files/hash-verify first, normalize metadata only, seal later."""
        self.check_capacity();files={}
        for p in sorted(self.directory.rglob('*')):
            if p.is_symlink():raise ValueError('Staged artifact symlinks are not permitted')
            if not p.is_file():continue
            rel=p.relative_to(self.directory)
            if rel.name=='result.json':continue
            target=self.destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
            digest=sha(p)
            # Frozen construction files may already exist; conflicting source
            # inputs are not silently replaced.
            if target.exists() and sha(target)!=digest:
                raise ValueError('Conflicting persistent artifact: '+str(rel))
            if not target.exists():shutil.copyfile(p,target)
            if sha(target)!=digest:raise ValueError('Transfer checksum mismatch')
            files[str(rel)]=digest
        result=self.directory/'result.json'
        if result.exists():
            digest=sha(result);shutil.copyfile(result,self.destination/'result.json')
            if sha(self.destination/'result.json')!=digest:raise ValueError('Result transfer checksum mismatch')
            files['result.json']=digest
        # Preserve originals before audited location-only projections.
        changes=[]
        def relocate(value):
            if isinstance(value,str) and (value==str(self.directory) or value.startswith(str(self.directory)+os.sep)):
                return str(self.destination)+value[len(str(self.directory)):]
            if isinstance(value,list):return [relocate(v) for v in value]
            if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
            return value
        for rel in ('result.json','capture/manifest.json'):
            path=self.destination/rel
            if not path.is_file():continue
            value=json.loads(path.read_text());projection=relocate(value)
            if projection!=value or rel=='result.json':
                original=self.destination/'storage-original-metadata'/rel
                original.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,original)
                atomic_result(path,projection);changes.append(rel)
        self.receipt.update(state='transferred',files=files,metadata_location_projections=changes,
                            transferred_at=time.time())
        atomic_result(self.registry,self.receipt)
        atomic_result(self.destination/'capture_staging.json',self.receipt)
        return self.receipt

    def cleanup(self):
        if self.receipt['state']!='transferred':raise ValueError('Untransferred evidence cannot be removed')
        verify_durable(self.receipt)
        shutil.rmtree(self.directory)
        self.receipt.update(state='cleaned',cleaned_at=time.time())
        atomic_result(self.registry,self.receipt)
        atomic_result(self.destination/'capture_staging.json',self.receipt)


def verify_durable(receipt):
    if receipt['state'] not in ('transferred','cleaned'):raise ValueError('Transfer not verified')
    destination=Path(receipt['destination']).resolve()
    for rel,digest in receipt['files'].items():
        path=destination/rel
        if rel in receipt.get('metadata_location_projections',[]):path=destination/'storage-original-metadata'/rel
        if destination not in path.resolve().parents or not path.is_file() or sha(path)!=digest:
            raise ValueError('Durable evidence verification failed: '+rel)


def owner_active(owner):
    if owner.get('node')!=socket.gethostname():return None
    if owner.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return False
    proc=Path('/proc')/str(owner['pid'])
    try:
        return proc.stat().st_uid==owner['uid'] and proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==owner['start_ticks']
    except FileNotFoundError:return False
    except OSError:return None


def cleanup(root):
    """Only registered inactive transferred directories; no age-based guessing."""
    root=Path(root).resolve();report=[]
    for registry in sorted(root.glob('attempt-*.json')):
        record=json.loads(registry.read_text())
        directory=Path(record['directory']).resolve()
        if record.get('format')!='owned-capture-stage-v1' or directory.parent!=root or record.get('owner',{}).get('uid')!=os.getuid() or registry.stat().st_uid!=os.getuid():continue
        active=owner_active(record['owner'])
        if active is not False or record['state']!='transferred':
            report.append({'directory':str(directory),'removed':False,'reason':'active, unknown owner, or untransferred evidence'});continue
        try:
            verify_durable(record)
            if directory.exists():shutil.rmtree(directory)
            record.update(state='cleaned',cleaned_at=time.time());atomic_result(registry,record)
            report.append({'directory':str(directory),'removed':True})
        except (OSError,ValueError) as exc:
            report.append({'directory':str(directory),'removed':False,'reason':str(exc)})
    return report
