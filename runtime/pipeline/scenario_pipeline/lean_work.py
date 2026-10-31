"""Transactional review-only workspaces; demo cases symlink to full-set cases."""
import argparse
from contextlib import ExitStack
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time

from batch_pipeline.store import atomic
from batch_pipeline.runtime_dependencies import coordinated_access
from recording_store import locked, safe_name, sha

SETS = ('demo-train', 'demo-test', 'full-train', 'full-test', 'held-out')
PARENTS = {'demo-train': 'full-train', 'demo-test': 'full-test'}
# Maintenance receipts are separate from set review outputs and membership.
AUXILIARY_DIRS = {'maintenance'}
FORMAT = 'set-review-workspaces-v2'


def read(p):
    return json.loads(Path(p).read_text())


def text(p, value):
    p = Path(p)
    if p.exists() and p.read_text() == value:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name+'.review-tmp')
    temp.write_text(value)
    temp.replace(p)


def members(root):
    return {s: [m for m in read(root/'sets'/s/'selection.json')['members']
                if m.get('status', 'accepted') == 'accepted'] for s in SETS}


def folder(m):
    return safe_name(m['cell_id'])+'--'+safe_name(m['law_id'])


def case_folder(m):
    rid = m['recording_id']
    if not re.fullmatch('[0-9a-f]{64}', rid):
        raise ValueError('Invalid recording ID')
    return safe_name(m['case_id'])+'--'+rid[:12]


def protected(root):
    return {str(p.relative_to(root)): sha(p) for s in SETS
            for p in [root/'sets'/s/'scope.json', root/'sets'/s/'selection.json']}


def ownership(root):
    result = []
    now = time.time()
    for path in sorted((root/'state').glob('*.sqlite')):
        db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
        try:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'runs', 'jobs'} <= tables:
                continue
            running = db.execute("SELECT id,stage,entity,lease_until FROM jobs WHERE status='running'").fetchall()
            if any(r[3] is None or r[3] > now for r in running):
                raise ValueError('Live or unbounded running job: '+str(path))
            leases = db.execute('SELECT resource,owner,expires FROM resource_leases').fetchall() if 'resource_leases' in tables else []
            if any(r[1] != 'unavailable' and r[2] > now for r in leases):
                raise ValueError('Live resource lease: '+str(path))
            result.append({'database': str(path), 'expired_running_rows_preserved': running,
                           'historical_leases_preserved': leases})
        finally:
            db.close()
    return result


def describe_plan(root, backup):
    ms = members(root)
    destinations = {}
    for s, rows in ms.items():
        for m in rows:
            key = (s, folder(m), case_folder(m))
            if key in destinations:
                raise ValueError('Destination collision: '+str(key))
            destinations[key] = m['recording_id']
            for name in ('video.webm', 'trace.json', 'metadata.json'):
                p = root/'recordings'/m['recording_id']/name
                if not p.is_file():
                    raise ValueError('Missing canonical primary: '+str(p))
    for child, parent in PARENTS.items():
        parent_keys = {(m['cell_id'], m['law_id'], m['actor'], m['case_id'], m['recording_id']) for m in ms[parent]}
        if not all((m['cell_id'], m['law_id'], m['actor'], m['case_id'], m['recording_id']) in parent_keys for m in ms[child]):
            raise ValueError('Demo membership is not a subset of '+parent)
    if root.stat().st_dev != backup.stat().st_dev:
        raise ValueError('Archive rename requires the same filesystem')
    return {'format': FORMAT, 'root': str(root), 'backup_root': str(backup),
            'accepted_memberships': {s: len(rows) for s, rows in ms.items()},
            'distinct_recordings': len({m['recording_id'] for rows in ms.values() for m in rows}),
            'set_hashes': protected(root), 'ownership': ownership(root),
            'old_work_directories': sorted(p.name for p in (root/'work').iterdir() if p.is_dir())}


def source_path(root, path, legacy):
    p = Path(path)
    if p.is_file():
        return p
    # Historical receipt strings may predate the workspace migration.
    marker = '/runs/scenario_pipeline/'
    if marker in str(p):
        suffix = str(p).split(marker, 1)[1]
        p = root/suffix
        if p.is_file():
            return p
        for old, new in legacy.get('recovery_sources', {}).items() if isinstance(legacy.get('recovery_sources'), dict) else []:
            if str(p).startswith(old+'/'):
                candidate = Path(new)/str(p)[len(old)+1:]
                if candidate.is_file():
                    return candidate
    return None


def receipt_references(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and value['path'].endswith('.json') and value.get('sha256'):
            yield value['path'], value['sha256']
        for k, v in value.items():
            if k.endswith('receipt') and isinstance(v, str) and v.endswith('.json'):
                yield v, value.get(k+'_sha256')
            elif isinstance(v, (dict, list)):
                yield from receipt_references(v)
    elif isinstance(value, list):
        for item in value:
            yield from receipt_references(item)


def build_models(root, staging, ms, legacy):
    from recording_readmes import RecordingReadmes, describe, differences, varying_assignments, comparison_title
    docs = RecordingReadmes(root, ms, set_ids=SETS)
    cache = {}
    try:
        for s, rows in ms.items():
            grouped = {}
            for m in rows:
                grouped.setdefault(folder(m), []).append(m)
            for name, group in sorted(grouped.items()):
                cell, law = group[0]['cell_id'], group[0]['law_id']
                ids = {m['recording_id'] for m in group}
                key = (cell, law, tuple(sorted(ids)))
                if key in cache:
                    model = cache[key]
                else:
                    entry = next((e for e in legacy.get('entries', []) if e['cell_id']==cell and e['law_id']==law and e['category']!='held-out'), None)
                    if not entry:
                        entry = next((e for e in legacy.get('entries', []) if e['cell_id']==cell and e['law_id']==law), None)
                    dest = root/entry['path'] if entry else root/'work'/s/name
                    records = [docs.records[rid] for rid in sorted(ids)]
                    comparisons = []
                    for gid, rr in sorted(docs.groups(records, dest).items()):
                        names = sorted({n for r in rr for n in differences(r['case']) if n}) or varying_assignments(rr)
                        items = []
                        for r in sorted(rr, key=lambda x: x['case']['case_id']):
                            item = {'recording_id': r['rid'], 'case_id': r['case']['case_id'],
                                    'description': describe(r, names, rr), 'judgments': r['judgments'],
                                    'reuse': bool(r['reuse']), 'receipt_sources': []}
                            if r['reuse']:
                                item['receipt_sources'].append({'path': str(r['reuse']), 'sha256': sha(r['reuse'])})
                            items.append(item)
                        comparisons.append({'id': gid, 'title': comparison_title(gid), 'cases': items})
                    model = {'law': docs.law(law), 'cell_id': cell, 'law_id': law, 'comparisons': comparisons}
                    cache[key] = model
                atomic(staging/s/name/'review.json', model)
        return docs
    except BaseException:
        docs.close()
        raise


def copy_primary(root, staging, s, m, journal, journal_path):
    dest = staging/s/folder(m)/case_folder(m)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ('video.webm', 'trace.json', 'metadata.json'):
        source = root/'recordings'/m['recording_id']/name
        target = dest/name
        key = str(target.relative_to(staging))
        saved = journal['files'].get(key)
        if saved:
            if not unchanged(target,saved) or not unchanged(source,saved):
                raise ValueError('Changed source or staged primary: '+key)
            continue
        before = source.stat()
        temp = target.with_name(name+'.copying')
        h = hashlib.sha256()
        with source.open('rb') as src, temp.open('wb') as dst:
            for block in iter(lambda: src.read(4*1024*1024), b''):
                h.update(block); dst.write(block)
        after = source.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('Source changed during copy: '+str(source))
        if sha(temp) != h.hexdigest():
            raise ValueError('Copy hash mismatch: '+key)
        shutil.copystat(source, temp)
        temp.replace(target)
        journal['files'][key] = {'sha256': h.hexdigest(), 'bytes': after.st_size,
                                 'source': str(source), 'source_mtime_ns': after.st_mtime_ns}
        atomic(journal_path, journal)


def unchanged(path, receipt):
    """Reuse the completed two-sided SHA check while its file fingerprint holds.

    Staging is private under the migration lock. This is only a cutover/resume
    check; editable review files have no fingerprint restriction after install.
    """
    try:
        stat=Path(path).stat()
    except FileNotFoundError:
        return False
    return stat.st_size==receipt['bytes'] and stat.st_mtime_ns==receipt['source_mtime_ns']


def render(root, index, *, work=None):
    from recording_readmes import cell, final_label
    work = Path(work) if work else root/'work'
    ms = members(root)
    top = ['# Review outputs', '', 'Demo recording folders link to their matching full-set folders. Edits through either path are shared.', '',
           '| Set | Accepted recordings |', '| --- | ---: |']
    for s in SETS:
        top.append('| ['+s+']('+s+'/README.md) | '+str(len(ms[s]))+' |')
        lines = ['# '+s, '', 'Accepted review outputs. Settings are authored facts or controller requests; labels are the saved expected scenario labels. Acceptance does not establish exhaustive statutory coverage.', '',
                 '| Cell | Law and comparisons | Videos |', '| --- | --- | ---: |']
        entries = [e for e in index['entries'] if e['set_id']==s]
        for e in entries:
            base = work/s/e['folder']
            model = read(base/'review.json')
            law = model['law']
            page = ['# '+e['cell_id']+' / '+e['law_id'], '', '## Law', '',
                    '**'+e['law_id']+(' — '+law.get('title') if law.get('title') else '')+'**', '',
                    '> '+law.get('text', 'Source text unavailable').replace('\n', '\n> '), '',
                    '## Recording comparisons', '',
                    'Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. '
                    'Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.', '']
            if model.get('viewing_note'):
                pos=page.index('## Recording comparisons');page[pos:pos]=['## How to watch', '', model['viewing_note'], '']
            show_ids=model.get('show_internal_ids',True)
            by_rid = {m['recording_id']:m for m in ms[s] if folder(m)==e['folder']}
            if model.get('labeling_note'):
                page += ['### Labeling convention', '', model['labeling_note'], '']
            for comparison in model['comparisons']:
                rr = [r for r in comparison['cases'] if r['recording_id'] in by_rid]
                page += ['### '+comparison['title'], '']
                if show_ids:page += ['Comparison: `'+comparison['id']+'`.', '']
                if comparison.get('description'):
                    page += [comparison['description'], '']
                page += ['| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |',
                         '| --- | --- | --- | --- | --- | --- |']
                for i, r in enumerate(rr, 1):
                    cf = case_folder(by_rid[r['recording_id']])
                    meta = read(base/cf/'metadata.json')
                    record = {'saved': meta.get('acceptance') or meta.get('published_record') or {}, 'metadata':meta, 'judgments':r['judgments']}
                    peers = ', '.join(str(j) for j in range(1,len(rr)+1) if j!=i) or 'No accepted counterpart'
                    judgment=r.get('judgment_resolution') or '; '.join(r['judgments']) or 'None listed'
                    page.append('| '+str(i)+' | [video]('+cf+'/video.webm) · [trace]('+cf+'/trace.json) · [metadata]('+cf+'/metadata.json) | '+cell(r['description']+((' (same reference video)' if not show_ids else ' (reused reference)') if r['reuse'] else ''))+' | '+peers+' | '+cell(judgment)+' | '+final_label(record)+' |')
                if show_ids:page += ['', 'Case IDs: '+'; '.join(str(i)+': `'+r['case_id']+'`' for i,r in enumerate(rr,1))+'.', '']
                else:page += ['']
            if model.get('trace_compatibility'):
                revision=model['trace_compatibility']
                page += ['## Trace compatibility update', '', revision['note'], '',
                         '| Case | Updated data | Validation |', '| --- | --- | --- |']
                for item in revision['recordings']:
                    page.append('| '+cell(item['case_id'])+' | [trace]('+item['trace']+') · [manifest]('+item['manifest']+') · [receipt]('+item['receipt']+') | '+cell(item['validation'])+' |')
                page += ['']
            remaining=model.get('remaining_requirements_note','Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.')
            page += ['## Remaining requirements', '', remaining, '']
            text(base/'README.md', '\n'.join(page))
            shown={r['recording_id'] for g in model['comparisons'] for r in g['cases']} & set(by_rid)
            count=len(shown) if model.get('final_collection') else len(by_rid)
            lines.append('| '+e['cell_id']+' | ['+e['law_id']+']('+e['folder']+'/README.md) | '+str(count)+' |')
        text(work/s/'README.md', '\n'.join(lines)+'\n')
    text(work/'README.md', '\n'.join(top)+'\n')


def verify(root, work, index, expected_hashes=None):
    ms = members(root)
    expected_dirs = set(SETS)
    actual_dirs = {p.name for p in work.iterdir() if p.is_dir()}
    if actual_dirs - AUXILIARY_DIRS != expected_dirs:
        raise ValueError('Unexpected work directories: '+str(actual_dirs))
    links = 0; count = 0
    for s, rows in ms.items():
        expected_cells = {folder(m) for m in rows}
        if {p.name for p in (work/s).iterdir() if p.is_dir()} != expected_cells:
            raise ValueError('Unexpected cell/law directories: '+s)
        for m in rows:
            d = work/s/folder(m)/case_folder(m)
            if s in PARENTS:
                target = work/PARENTS[s]/folder(m)/case_folder(m)
                if not d.is_symlink() or os.path.isabs(os.readlink(d)) or d.resolve()!=target.resolve():
                    raise ValueError('Wrong demo symlink: '+str(d))
                links += 1
            elif d.is_symlink():
                raise ValueError('Full-set case must be a real directory')
            for name in ('video.webm', 'trace.json', 'metadata.json'):
                p = d/name
                if not p.is_file() or p.is_symlink():
                    raise ValueError('Missing or nonregular primary: '+str(p))
                if expected_hashes and s not in PARENTS:
                    expected = expected_hashes[str(p.relative_to(work))]
                    if not unchanged(p,expected):
                        raise ValueError('Output hash changed: '+str(p))
            count += 1
    broken = []
    review_readmes = [work/'README.md']
    for set_id in SETS:
        review_readmes += [work/set_id/'README.md'] + list((work/set_id).glob('*/README.md'))
    for p in review_readmes:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if not (p.parent/link).exists():
                broken.append(str(p.parent/link))
    if broken:
        raise ValueError('Broken review links: '+str(broken[:10]))
    return {'accepted_memberships':count,'demo_directory_symlinks':links,'distinct_recordings':len({m['recording_id'] for rows in ms.values() for m in rows}),'broken_links':0,'auxiliary_directories_preserved':sorted(actual_dirs & AUXILIARY_DIRS)}


def relocate_databases(root, old_work, archived, receipt_dir, journal, journal_path):
    for item in journal['plan']['ownership']:
        path = Path(item['database'])
        key = str(path)
        if key in journal.get('databases', {}):
            continue
        db = sqlite3.connect(path)
        try:
            def relocated(value):
                normalized=Path(value).resolve()
                return str(archived/normalized.relative_to(old_work)) if normalized.is_relative_to(old_work) else None
            plan=journal.get('database_plans',{}).get(key)
            if plan is None:
                changed=[(run,output,relocated(output)) for run,output in db.execute('SELECT id,output FROM runs') if relocated(output)]
                attempts=[]
                tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'attempts' in tables:
                    for jid,number,raw in db.execute('SELECT job_id,number,metadata FROM attempts WHERE metadata IS NOT NULL'):
                        value=json.loads(raw)
                        directory=value.get('directory') if isinstance(value,dict) else None
                        if directory and relocated(directory):
                            value['directory']=relocated(directory)
                            attempts.append((jid,number,raw,json.dumps(value,sort_keys=True)))
                plan={'run_output_changes':changed,'attempt_location_changes':attempts}
                journal.setdefault('database_plans',{})[key]=plan
                atomic(journal_path,journal)
            changed=plan['run_output_changes'];attempts=plan['attempt_location_changes']
            if not changed and not attempts:
                continue
            backup = receipt_dir/'databases'/path.name
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():
                target = sqlite3.connect(backup)
                try:
                    db.backup(target)
                    if target.execute('pragma integrity_check').fetchall()!=[('ok',)]:
                        raise ValueError('Database backup integrity failed')
                finally:
                    target.close()
            for run, old, new in changed:
                db.execute('UPDATE runs SET output=? WHERE id=? AND output=?',(new,run,old))
            for jid,number,old,new in attempts:
                db.execute('UPDATE attempts SET metadata=? WHERE job_id=? AND number=? AND metadata=?',(new,jid,number,old))
            db.commit()
            journal.setdefault('databases', {})[key] = {'backup':str(backup),'backup_sha256':sha(backup),'run_output_changes':changed,'attempt_locations_updated':len(attempts)}
            atomic(journal_path,journal)
        finally:
            db.close()


def migrate(root, backup, *, apply=False):
    root = Path(root).resolve();backup = Path(backup).resolve()
    journal_path = root/'state/lean-work-migration.json'
    if (root/'work/index.json').exists() and read(root/'work/index.json').get('format')==FORMAT and (not journal_path.exists() or read(journal_path)['status']=='completed'):
        result = verify(root,root/'work',read(root/'work/index.json'))
        return dict(result,completed=True,already_migrated=True)
    if not apply:
        return describe_plan(root,backup)
    with ExitStack() as stack:
        stack.enter_context(coordinated_access(editing=True,path=root/'state/runtime-edit.lock'))
        for name in ['workspace-migration.lock','workspace-navigation.lock','law-split-migration.lock','scene-intent-separation.lock']+[ 'set-'+s+'.lock' for s in SETS]:
            stack.enter_context(locked(root/'state'/name))
        if journal_path.exists():
            journal = read(journal_path)
            if journal['plan']['backup_root']!=str(backup):
                raise ValueError('Resume backup root differs')
        else:
            plan = describe_plan(root,backup)
            ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            journal = {'status':'staging','id':ident,'plan':plan,'files':{},'databases':{}}
            atomic(journal_path,journal)
        ident=journal['id'];work=root/'work';staging=root/('work-staging-'+ident)
        archived=backup/'runs/scenario_pipeline/work'/ident
        receipt_dir=backup/'archive-receipts'/('lean-work-'+ident)
        if protected(root)!=journal['plan']['set_hashes']:
            raise ValueError('Set membership/scope changed during migration')
        ownership(root)
        if journal['status']=='staging':
            legacy=read(work/'index.json');ms=members(root);staging.mkdir(exist_ok=True)
            docs=build_models(root,staging,ms,legacy)
            try:
                unique={m['recording_id'] for s in SETS if s not in PARENTS for m in ms[s]}
                done=0
                for s in SETS:
                    if s in PARENTS:continue
                    for m in ms[s]:
                        copy_primary(root,staging,s,m,journal,journal_path);done+=1
                        if done%10==0:print(json.dumps({'copied_recordings':done,'distinct_recordings':len(unique)}),flush=True)
                        d=staging/s/folder(m)/case_folder(m);refs=list(receipt_references(m))+list(receipt_references(docs.records[m['recording_id']]['metadata']))
                        for comparison in read(staging/s/folder(m)/'review.json')['comparisons']:
                            for item in comparison['cases']:
                                if item['recording_id']==m['recording_id']:
                                    refs += [(r['path'],r.get('sha256')) for r in item['receipt_sources']]
                        receipt_index=[]
                        for source, expected in refs:
                            p=source_path(root,source,legacy)
                            if not p or p.stat().st_size>8*1024*1024:
                                receipt_index.append({'historical_source':source,'local_copy':None,'reason':'historical source unavailable or exceeds compact receipt limit'})
                                continue
                            digest=sha(p)
                            if expected and expected!=digest:raise ValueError('Receipt source hash differs: '+source)
                            target=d/'receipts'/(digest[:12]+'-'+p.name);target.parent.mkdir(exist_ok=True)
                            if not target.exists():shutil.copy2(p,target)
                            receipt_index.append({'historical_source':source,'local_copy':target.name,'sha256':digest})
                        atomic(d/'receipts/index.json',receipt_index)
            finally:docs.close()
            entries=[]
            for s, rows in ms.items():
                (staging/s).mkdir(exist_ok=True)
                grouped={}
                for m in rows:
                    grouped.setdefault(folder(m),[]).append(m)
                    if s in PARENTS:
                        link=staging/s/folder(m)/case_folder(m);link.parent.mkdir(exist_ok=True)
                        target=staging/PARENTS[s]/folder(m)/case_folder(m)
                        if not link.is_symlink():link.symlink_to(os.path.relpath(target,link.parent),target_is_directory=True)
                for name, rr in sorted(grouped.items()):
                    entries.append({'set_id':s,'folder':name,'cell_id':rr[0]['cell_id'],'law_id':rr[0]['law_id'],'recording_ids':[m['recording_id'] for m in rr],'path':'work/'+s+'/'+name})
            campaigns={run:str(archived/Path(path).relative_to('work')) for run,path in legacy.get('campaigns',{}).items()}
            index={'format':FORMAT,'entries':entries,'campaigns':campaigns,'resources':legacy.get('resources',{}),'archive_root':str(archived),'migration_receipt':str(receipt_dir/'receipt.json'),'sets':list(SETS),'assignments':{}}
            atomic(staging/'index.json',index);render(root,index,work=staging)
            verified=verify(root,staging,index,journal['files'])
            if protected(root)!=journal['plan']['set_hashes']:raise ValueError('Selections changed')
            # Source primaries must still match the verified copies at cutover.
            for item in journal['files'].values():
                p=Path(item['source'])
                if not unchanged(p,item):
                    raise ValueError('Canonical source changed during staging: '+str(p))
            ownership(root);journal.update(status='ready',verification=verified);atomic(journal_path,journal)
        receipt_dir.mkdir(parents=True,exist_ok=True)
        if journal['status']=='ready':
            archived.parent.mkdir(parents=True,exist_ok=True)
            if work.exists() and archived.exists():raise ValueError('Archive destination already exists')
            if work.exists():work.rename(archived)
            journal['status']='archived';atomic(journal_path,journal)
        if journal['status']=='archived':
            if not work.exists():staging.rename(work)
            if read(work/'index.json').get('format')!=FORMAT:raise ValueError('Unrecognized cutover tree')
            journal['status']='installed';atomic(journal_path,journal)
        if journal['status']=='installed':
            relocate_databases(root,work,archived,receipt_dir,journal,journal_path)
            set_index=read(root/'sets/index.json');set_index['workspace_categories']={s:s for s in SETS};set_index['workspace_layout']=FORMAT;atomic(root/'sets/index.json',set_index)
            journal['verification']=verify(root,work,read(work/'index.json'),journal['files'])
            if protected(root)!=journal['plan']['set_hashes']:raise ValueError('Protected set files changed')
            journal.update(status='completed',archive_root=str(archived),completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),canonical_recordings_unchanged=True)
            atomic(receipt_dir/'receipt.json',journal);atomic(journal_path,journal)
        return {'completed':True,'archive_root':str(archived),'receipt':str(receipt_dir/'receipt.json'),**journal['verification']}


def refresh(root):
    root=Path(root);index=read(root/'work/index.json');ms=members(root)
    expected={(s,m['recording_id']) for s,rows in ms.items() for m in rows}
    current={(e['set_id'],rid) for e in index['entries'] for rid in e['recording_ids']}
    if expected!=current:
        raise ValueError('Accepted membership changed; materialize new review outputs explicitly before refreshing')
    render(root,index)
    return dict(verify(root,root/'work',index),implementation_files_changed=0,recording_copies=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--backup',required=True,type=Path);p.add_argument('--apply',action='store_true')
    a=p.parse_args();print(json.dumps(migrate(a.root,a.backup,apply=a.apply),indent=2))

if __name__=='__main__':main()
