"""Git-only update publication and deterministic pause/resume interpretation."""
import subprocess
from pathlib import Path
from .common import read, write, sha, tree, within


def state(repo):
    repo=Path(repo); batch=read(repo/'batch.json'); paused=set(); seen=[]
    for path in sorted((repo/'updates').glob('[0-9][0-9][0-9].json')):
        notice=read(path)
        if notice['batch_id']!=batch['batch_id']:
            continue
        if notice['version']>batch['update_version']:
            raise ValueError('Notice newer than manifest')
        scope=set(batch['assignments']) if notice['assignments']=='all' else set(notice['assignments'])
        if not scope <= set(batch['assignments']):
            raise ValueError('Update includes unassigned work')
        action=notice['action']
        if action=='pause-all': paused=set(batch['assignments'])
        elif action=='pause-affected': paused|=scope
        elif action=='resume': paused-=scope
        elif action!='continue': raise ValueError('Unknown action')
        seen.append(notice['version'])
    if 'initial_update_version' in batch and seen != list(range(batch['initial_update_version'],batch['update_version']+1)):
        raise ValueError('Skipped/missing numbered update')
    if seen and seen[-1]!=batch['update_version']:
        raise ValueError('Missing current update notice')
    return {'version':batch['update_version'],'seen':seen,'paused_assignments':sorted(paused)}


def publish(repo, notice_file, changed_files, receipt_root, push=False):
    repo=Path(repo).resolve()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    if git('branch','--show-current')!='main': raise ValueError('Publish from main only')
    git('fetch','origin','main')
    if git('rev-parse','HEAD')!=git('rev-parse','origin/main'): raise ValueError('Reconcile remote main before publication')
    # HEAD is the trusted baseline; edited working manifest is never authority.
    import json,hashlib
    original=git('show','HEAD:batch.json');old=json.loads(original)
    if read(repo/'batch.json')!=old: raise ValueError('Do not manually edit batch.json')
    files=set(changed_files)
    for rel in files:
        if not rel.startswith(('skills/','inputs/','runtime/','examples/','tests/','START_HERE.md','worker_check.py')):
            raise ValueError('Update file outside permitted inputs/code')
        within(repo,rel)
    dirty=set(git('diff','--name-only','HEAD').splitlines()) | set(git('ls-files','--others','--exclude-standard').splitlines())
    if dirty!=files: raise ValueError('Declare exactly the changed files; unrelated changes must not be staged')
    notice=read(notice_file);version=old['update_version']+1
    if notice['batch_id']!=old['batch_id'] or notice['version']!=version: raise ValueError('Wrong update identity')
    if notice.get('action') not in ('continue','pause-affected','pause-all','resume') or not notice.get('instructions'):
        raise ValueError('Missing action/instructions')
    prior=f'updates/manifests/{old["update_version"]:03d}.json'
    write(repo/prior,old)
    notice_path=f'updates/{version:03d}.json';write(repo/notice_path,notice)
    (repo/'UPDATE.md').write_text(f'# Updates\nProcess unseen numbered JSON notices in order through {version:03d}. Run python3 update_status.py.\n')
    batch=dict(old,update_version=version,parent_manifest_sha256=sha(repo/prior))
    batch['frozen_files']={k:v for k,v in tree(repo).items() if k!='batch.json' and not k.startswith('work/')}
    write(repo/'batch.json',batch)
    state(repo)
    from .preparation import check
    check(repo)
    approved=sorted(files|{prior,notice_path,'UPDATE.md','batch.json'})
    git('add','--',*approved)
    if set(git('diff','--cached','--name-only').splitlines())!=set(approved):
        raise ValueError('Unexpected staged changes')
    git('commit','-m',f'Publish worker update {version:03d}')
    previous_path=Path(receipt_root)/old['batch_id']/'export.json'
    previous=read(previous_path) if previous_path.exists() else {}
    receipt={'local_snapshots':previous.get('local_snapshots',{}),'batch':batch,'batch_sha256':sha(repo/'batch.json'),'project_root':str(Path(__file__).resolve().parents[2])}
    target=Path(receipt_root)/old['batch_id']
    write(target/f'export-update-{version:03d}.json',receipt);write(target/'export.json',receipt)
    if push: git('push','origin','main')
    return {'version':version,'commit':git('rev-parse','HEAD'),'pushed':push}


def main():
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--notice',type=Path,required=True)
    p.add_argument('--file',action='append',default=[]);p.add_argument('--receipt-root',type=Path,required=True);p.add_argument('--push',action='store_true')
    a=p.parse_args();print(json.dumps(publish(a.repo,a.notice,a.file,a.receipt_root,a.push),indent=2))
if __name__=='__main__': main()
