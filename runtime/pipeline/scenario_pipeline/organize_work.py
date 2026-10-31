"""Verified, copy-only migration of implementation work into cell/law workspaces."""
import argparse
import ast
from contextlib import ExitStack, nullcontext
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time

from batch_pipeline.store import atomic
from pipeline_paths import OUTPUT_ROOT
from recording_store import identity, locked, sha

SETS = {'demo-train': 'demo', 'demo-test': 'demo', 'held-out': 'held-out', 'full-train': 'train', 'full-test': 'test'}
CATEGORIES = ('demo', 'held-out', 'train', 'test')
SKIP = {'.git', '.lake', '__pycache__', 'node_modules', 'envs', 'venv', 'sdk', 'SDK', 'CarlaUE4',
        'PythonAPI', 'original', 'evidence', 'recordings', 'frames', 'rgb', 'graphs', 'scene_graphs',
        'runtime', 'runtime_versions', 'decoder', 'capture', 'sensors', 'build', 'dist', 'site-packages'}
EXTENSIONS = {'.py', '.lean', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.csv',
              '.sql', '.sh', '.xodr', '.xml', '.html', '.css', '.js', '.c', '.cpp', '.h'}
LAW = re.compile(r'NRS-\d+[A-Z]?-[\dA-Za-z]+(?:-[\dA-Za-z]+)*|LVMC-\d+-\d+-[\dA-Za-z]+(?:-[\dA-Za-z]+)*')
CELL = re.compile(r'C\d+')
MAX_TEXT = 8 * 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text())


def category_for(split, law, demo_laws):
    if split == 'heldout': return 'held-out'
    if law in demo_laws: return 'demo'
    return 'test' if split == 'testing' else 'train'


def live_databases(root):
    databases = []
    for path in sorted((root/'state').glob('*.sqlite')):
        db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)
        try:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'runs','jobs'} <= tables: continue
            if db.execute("SELECT 1 FROM jobs WHERE status='running' AND lease_until>? LIMIT 1", (time.time(),)).fetchone():
                raise ValueError('Active campaign job: '+str(path))
            if 'resource_leases' in tables and db.execute("SELECT 1 FROM resource_leases WHERE owner!='unavailable' AND expires>? LIMIT 1", (time.time(),)).fetchone():
                raise ValueError('Active campaign lease: '+str(path))
            databases.append((path, db.execute('SELECT id,output FROM runs').fetchall()))
        finally:
            db.close()
    return databases


def primary_law(source, candidates):
    """Use an explicit handoff title; never choose arbitrarily between laws."""
    files = list(source.glob('HANDOFF-current-v*.txt'))
    files.sort(key=lambda p: int(re.search(r'-v(\d+)', p.name)[1]), reverse=True)
    files += [source/'HANDOFF.md', source/'README.md']
    for path in files:
        if path.is_file():
            with path.open(errors='replace') as stream: head=stream.read(500)
            match = LAW.search(head)
            if match: return match.group()
    for path in sorted(source.glob('C*-cases.json')):
        hint=re.search(r'C\d+-(\d{3})-(\d+[a-z]?)',path.name)
        if hint:
            law='NRS-484B-'+hint[1]+'-'+hint[2]
            if law in candidates: return law
    match = LAW.search(source.name)
    if match: return match.group()
    suffix = re.search(r'C\d+-(\d{3})-(\d)', source.name)
    if suffix: return 'NRS-484B-'+suffix[1]+'-'+suffix[2]
    return next(iter(candidates)) if len(candidates)==1 else None


def prepare(root):
    assignments = {}
    inputs = {}
    memberships = {}
    scopes = {}
    demo_laws = set(read(root/'sets/demo-train/scope.json')['law_ids'])
    for set_id, _ in SETS.items():
        scope_path = root/'sets'/set_id/'scope.json'
        selection_path = root/'sets'/set_id/'selection.json'
        scope = read(scope_path); selection = read(selection_path)
        scopes[set_id] = scope
        inputs[str(scope_path.relative_to(root))] = sha(scope_path)
        inputs[str(selection_path.relative_to(root))] = sha(selection_path)
        memberships[set_id] = selection['members']
        for item in scope.get('assignments', []) + selection['members']:
            cell, law, actor = item['cell_id'], item['law_id'], item['actor']
            category = category_for(scope['split'], law, demo_laws)
            key = '|'.join((cell, law, actor))
            # Held-out exceptions can share a cell/law/actor with training.
            storage_key = category+'|'+key
            entry = assignments.setdefault(storage_key, {'category':category,'cell_id':cell,'law_id':law,'actor':actor,
                                                         'set_ids':[], 'recording_ids':[], 'sources':[], 'shared_sources':[]})
            if set_id not in entry['set_ids']: entry['set_ids'].append(set_id)
            if item.get('recording_id') and item.get('status','accepted')=='accepted' and item['recording_id'] not in entry['recording_ids']:
                entry['recording_ids'].append(item['recording_id'])
    owners = {}
    for set_id in ('full-train','full-test','held-out'):
        for cell in scopes[set_id]['precomputed_cell_ids']:
            owners[cell] = scopes[set_id]['split']
    groups = {}
    for e in assignments.values():
        e['path'] = str(Path('work')/e['category']/e['cell_id']/e['law_id'])
        groups.setdefault((e['category'],e['cell_id'],e['law_id']), []).append(e)
    campaigns = {}
    mappings = []
    sources = []
    work = root/'work'

    def add_source(source, destination, entries, *, shared=False):
        if not source.exists(): return
        rel = str(destination.relative_to(root))
        sources.append({'source':str(source),'destination':str(destination),'shared':shared})
        mappings.append((str(source), str(destination)))
        for entry in entries:
            field = 'shared_sources' if shared else 'sources'
            if rel not in entry[field]: entry[field].append(rel)

    # Campaign directories are discovered by their operational run.json, not by
    # whichever historical campaign happened to publish the latest export.
    for campaign in sorted(work.iterdir()):
        if not campaign.is_dir() or campaign.name in CATEGORIES or campaign.name.startswith('_'): continue
        if not (campaign/'run.json').exists(): continue
        cat = 'held-out' if 'held' in campaign.name else ('demo' if 'demo' in campaign.name else 'train')
        dest = work/cat/'_campaigns'/campaign.name
        campaigns[campaign.name] = str(dest.relative_to(root))
        mappings.append((str(campaign),str(dest)))
        direct = []
        for child in sorted(campaign.iterdir()):
            if not child.is_dir() or not CELL.fullmatch(child.name.split('-')[0]): continue
            cell = CELL.search(child.name)[0]
            entries = [e for e in assignments.values() if e['cell_id']==cell]
            candidates = {e['law_id'] for e in entries if e['category']==cat}
            law = primary_law(child, candidates)
            relevant = [e for e in entries if e['law_id']==law and e['category']==cat] if law else []
            target = work/cat/cell/(law if law else '_shared')/'sources'/campaign.name/child.name
            add_source(child,target,relevant if law else entries,shared=law is None)
            direct.append(child.name)
        for cell in sorted((campaign/'cells').iterdir()) if (campaign/'cells').exists() else []:
            if not cell.is_dir(): continue
            entries = [e for e in assignments.values() if e['cell_id']==cell.name]
            owner = owners.get(cell.name)
            shared_cat = 'held-out' if cat=='held-out' else ('demo' if any(e['category']=='demo' for e in entries) else ('test' if owner=='testing' else cat))
            target = work/shared_cat/cell.name/'_shared/semantic'/campaign.name
            add_source(cell,target,entries,shared=True)
        sources.append({'source':str(campaign),'destination':str(dest),'campaign':True,'exclude':direct+['cells']})

    # Frozen dated bundles contain prior completed implementation, not just data.
    bundle_root = root/'inputs/bundles'
    for family in sorted(bundle_root.iterdir()) if bundle_root.exists() else []:
        if not family.is_dir() or family.name in ('set-organization', 'workspace-migration'): continue
        for source in sorted(family.iterdir()):
            if not source.is_dir(): continue
            match = CELL.search(source.name)
            if not match:
                hints={CELL.search(p.name)[0] for p in source.glob('C*-cases.json') if CELL.search(p.name)}
                if len(hints)!=1: continue
                cell=next(iter(hints))
            else:
                cell=match[0]
            entries=[e for e in assignments.values() if e['cell_id']==cell]
            if not entries: continue
            cat = 'held-out' if 'held' in family.name else ('demo' if 'demo' in family.name else 'train')
            candidates={e['law_id'] for e in entries if e['category']==cat}
            law=primary_law(source,candidates)
            relevant=[e for e in entries if e['law_id']==law and e['category']==cat] if law else entries
            dest=work/cat/cell/(law if law else '_shared')/'sources'/family.name/source.name
            add_source(source,dest,relevant,shared=law is None)
    return assignments, campaigns, sources, mappings, inputs, memberships


def walk_source(item):
    source=Path(item['source']); destination=Path(item['destination'])
    for base, dirs, files in os.walk(source, followlinks=False):
        relative=Path(base).relative_to(source)
        dirs[:]=sorted(n for n in dirs if n not in SKIP and not n.startswith(('engine-', 'saved-render-', '.'))
                       and not (relative==Path('.') and n in item.get('exclude',[])))
        for name in sorted(files):
            path=Path(base)/name
            if path.is_symlink() or path.suffix not in EXTENSIONS or path.stat().st_size>MAX_TEXT: continue
            if name.endswith(('.lock','.sqlite')): continue
            yield path,destination/relative/name


@lru_cache(maxsize=2)
def path_pattern(keys):
    return re.compile('|'.join(re.escape(p) for p in sorted(keys,key=len,reverse=True)))


def rewrite(text, mappings):
    # A single replacement avoids accidentally applying a shorter prefix inside
    # an already relocated path. JSON evidence and receipts remain byte-exact.
    table={a:b for a,b in mappings if '/inputs/' not in a or a==b}
    pattern=path_pattern(tuple(table)) if table else None
    return pattern.sub(lambda m:table[m[0]],text) if pattern else text



@lru_cache(maxsize=2)
def python_mappings(mappings):
    moved=[(a,b) for a,b in mappings if a!=b]
    expanded=list(mappings)
    for old,same in mappings:
        if old!=same: continue
        parents=[(a,b) for a,b in moved if old.startswith(a+'/')]
        if parents:
            a,b=max(parents,key=lambda pair:len(pair[0]))
            expanded.append((b+old[len(a):],old))
    return tuple(expanded)


def copied_location(source,mappings):
    source=str(source)
    matches=[(a,b) for a,b in mappings if source==a or source.startswith(a+'/')]
    if not matches: return source
    a,b=max(matches,key=lambda pair:len(pair[0]))
    return b+source[len(a):]


def rewrite_python(text, source, mappings):
    """Relocate statically known Path expressions without executing source."""
    tree=ast.parse(text)
    original_mappings=mappings
    mappings=python_mappings(tuple(mappings))
    known={'__file__':copied_location(source,original_mappings)}

    def value(node):
        if isinstance(node,ast.Constant): return node.value
        if isinstance(node,ast.Name): return known[node.id]
        if isinstance(node,ast.BinOp):
            left,right=value(node.left),value(node.right)
            if isinstance(node.op,ast.Div) and isinstance(left,Path): return left/right
            if isinstance(node.op,ast.Add) and isinstance(left,str) and isinstance(right,str): return left+right
        if isinstance(node,ast.Call) and not node.keywords:
            if isinstance(node.func,ast.Name) and node.func.id=='Path' and len(node.args)==1:
                return Path(value(node.args[0]))
            if isinstance(node.func,ast.Attribute) and node.func.attr=='resolve' and not node.args:
                obj=value(node.func.value)
                if isinstance(obj,Path): return obj.resolve()
        if isinstance(node,ast.Attribute):
            obj=value(node.value)
            if isinstance(obj,Path) and node.attr=='parent': return obj.parent
        raise ValueError('Not a static path')

    def bind(module):
        for node in module.body:
            if isinstance(node,ast.Assign):
                try: resolved=value(node.value)
                except (KeyError,ValueError,TypeError): continue
                for target in node.targets:
                    if isinstance(target,ast.Name): known[target.id]=resolved
    common=Path(source).parent/'common.py'
    if (any(isinstance(n,ast.ImportFrom) and n.module=='common' for n in tree.body)
            and common.is_file() and common!=Path(source)):
        known['__file__']=copied_location(common,original_mappings)
        bind(ast.parse(common.read_text()))
        known['__file__']=copied_location(source,original_mappings)
    bind(tree)
    local_scopes=[]
    for function in ast.walk(tree):
        if isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):
            local={n.id for n in ast.walk(function) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
            local.update(a.arg for a in function.args.args+function.args.kwonlyargs+function.args.posonlyargs)
            globals_={name for n in ast.walk(function) if isinstance(n,ast.Global) for name in n.names}
            local_scopes.append((function.lineno,function.end_lineno,local-globals_))
    encoded=text.encode();offsets=[0]
    for line in text.splitlines(keepends=True): offsets.append(offsets[-1]+len(line.encode()))
    edits=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.BinOp,ast.Call,ast.Attribute)): continue
        try: resolved=value(node)
        except (KeyError,ValueError,TypeError,OSError): continue
        if not isinstance(resolved,Path): continue
        names={n.id for n in ast.walk(node) if isinstance(n,ast.Name)}
        if any(start<=node.lineno<=end and names & local for start,end,local in local_scopes): continue
        relocated=rewrite(str(resolved),mappings)
        depends_on_file=any(isinstance(n,ast.Name) and n.id=='__file__' for n in ast.walk(node))
        if relocated==str(resolved) and not depends_on_file: continue
        start=offsets[node.lineno-1]+node.col_offset
        end=offsets[node.end_lineno-1]+node.end_col_offset
        edits.append((start,end,('Path('+repr(relocated)+')').encode()))
    result=[];position=0
    for start,end,replacement in sorted(edits,key=lambda e:(e[0],-e[1])):
        if start<position: continue
        result.extend((encoded[position:start],replacement));position=end
    result.append(encoded[position:])
    return rewrite(b''.join(result).decode(),mappings)


def organize_work(root=None, *, apply=False):
    root=(Path(root) if root is not None else OUTPUT_ROOT).resolve()
    from law_split import active_manifest
    if active_manifest(root):
        raise ValueError('Law-scoped workspaces are active; use refresh-workspaces instead of replaying bootstrap')
    with ExitStack() as stack:
        if apply:
            stack.enter_context(locked(root/'state/runtime-edit.lock'))
            stack.enter_context(locked(root/'state/workspace-migration.lock'))
        databases=live_databases(root)
        assignments,campaigns,sources,mappings,inputs,memberships=prepare(root)
        if apply:
            for item in sources:
                source=Path(item['source'])
                for path in sorted(source.glob('*.lock')):
                    stack.enter_context(locked(path))
        files=[]; seen={}
        # Pruned SDK/build/native resources remain frozen dependencies. Do not
        # rewrite their references into directories deliberately not copied.
        for item in sources:
            base=Path(item['source'])
            for path,dirs,_ in os.walk(base,followlinks=False):
                omitted=[n for n in dirs if n in SKIP or n.startswith(('engine-','saved-render-','.'))]
                for name in omitted:
                    original=str(Path(path)/name)
                    mappings.append((original,original))
                dirs[:]=[n for n in dirs if n not in omitted and not (Path(path)==base and n in item.get('exclude',[]))]
        for item in sources:
            for source,dest in walk_source(item):
                if str(source) in seen: continue
                seen[str(source)]=str(dest)
                files.append((source,dest))
        estimate=sum(source.stat().st_size for source,_ in files)
        report={'files':len(files),'copy_bytes':estimate,'workspaces':len({e['path'] for e in assignments.values()}),
                'campaigns':len(campaigns),'source_groups':len(sources),'apply':apply}
        if not apply: return report
        if shutil.disk_usage(root).free<estimate+128*1024*1024:
            raise ValueError('Insufficient space for independent implementation copies')
        journal=sqlite3.connect(root/'state/workspace-migration.sqlite')
        journal.execute('CREATE TABLE IF NOT EXISTS copies(source TEXT PRIMARY KEY,destination TEXT,source_sha256 TEXT,destination_sha256 TEXT,size INTEGER,mtime INTEGER)')
        rewritten=0
        unsupported_sources=[]
        try:
            for number,(source,dest) in enumerate(files):
                stat=source.stat(); digest=sha(source)
                old=journal.execute('SELECT destination,source_sha256,destination_sha256 FROM copies WHERE source=?',(str(source),)).fetchone()
                if old:
                    if old[0]!=str(dest) or old[1]!=digest or not dest.is_file() or sha(dest)!=old[2]:
                        raise ValueError('Source or destination changed independently; preserve and version it: '+str(source))
                    continue
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():
                    raise ValueError('Destination already exists without a journal record: '+str(dest))
                shutil.copy2(source,dest)
                if sha(dest)!=digest: raise ValueError('Copy verification failed: '+str(source))
                if source.suffix in ('.py','.sh'):
                    text=dest.read_text(errors='strict')
                    try:
                        updated=rewrite_python(text,source,mappings) if source.suffix=='.py' else rewrite(text,mappings)
                    except SyntaxError as error:
                        updated=text
                        unsupported_sources.append({'source':str(source),'reason':str(error),'retained_unchanged':True})
                    if updated!=text:
                        dest.write_text(updated); rewritten+=1
                if source.stat().st_mtime_ns!=stat.st_mtime_ns or source.stat().st_size!=stat.st_size:
                    raise ValueError('Source changed during copy; cutover deferred: '+str(source))
                journal.execute('INSERT INTO copies VALUES(?,?,?,?,?,?)',(str(source),str(dest),digest,sha(dest),stat.st_size,stat.st_mtime_ns))
                if number%100==0:
                    journal.commit()
                    print(json.dumps({'phase':'copy','files':number,'total':len(files)}),flush=True)
            journal.commit()
            # Recheck all source fingerprints before changing operational routing.
            for source,mtime,size in journal.execute('SELECT source,mtime,size FROM copies'):
                s=Path(source).stat()
                if (s.st_mtime_ns,s.st_size)!=(mtime,size): raise ValueError('Source changed before cutover: '+source)
            for rel,digest in inputs.items():
                if sha(root/rel)!=digest: raise ValueError('Set changed during migration: '+rel)
            live_databases(root)
            old_receipt=root/'state/workspace-migration.json'
            if old_receipt.exists():
                previous=read(old_receipt)
                if (previous.get('source_hashes')==inputs and previous.get('files')==len(files)
                        and (root/'work/index.json').exists()
                        and previous.get('index_sha256')==sha(root/'work/index.json')
                        and all(output==str(root/campaigns[run]) for _,rows in databases for run,output in rows if run in campaigns)):
                    return previous
            changes=[]
            for path,rows in databases:
                pending=[]
                for run,output in rows:
                    target=campaigns.get(run)
                    if target and output!=str(root/target): pending.append((run,output,str(root/target)))
                if not pending: continue
                backup=root/'inputs/database-snapshots/workspace-migration'/path.name
                if not backup.exists():
                    backup.parent.mkdir(parents=True,exist_ok=True)
                    src=sqlite3.connect(path); dst=sqlite3.connect(backup)
                    src.backup(dst);dst.close();src.close()
                db=sqlite3.connect(path)
                with db:
                    for run,old,new in pending:
                        db.execute('UPDATE runs SET output=? WHERE id=? AND output=?',(new,run,old))
                        changes.append({'database':path.name,'run':run,'old_output':old,'output':new})
                db.close()
            # Only operational locator strings in copied mutable indices change.
            def relocate(value):
                if isinstance(value,str): return rewrite(value,mappings)
                if isinstance(value,list): return [relocate(v) for v in value]
                if isinstance(value,dict): return {k:relocate(v) for k,v in value.items()}
                return value
            for target in campaigns.values():
                for name in ('run.json','delivery_index.json'):
                    path=root/target/name
                    if path.exists():
                        atomic(path,relocate(read(path)))
                        journal.execute('UPDATE copies SET destination_sha256=? WHERE destination=?',(sha(path),str(path)))
            journal.commit()
            # Preserve set scopes/selections: navigation is the only set edit.
            index={'format':'workspaces-v1','campaigns':campaigns,'entries':sorted(assignments.values(),key=lambda e:e['path']+'|'+e['actor']),
                   'assignments':{},'set_sources':inputs,'recovery_sources':[str(Path(s['source']).relative_to(root)) for s in sources],
                   'copied_files':len(files),'copied_bytes':estimate}
            index['resources']=freeze_campaign_resources(root,campaigns)
            for entry in assignments.values():
                key='|'.join((entry['cell_id'],entry['law_id'],entry['actor']))
                if entry['category']!='held-out': index['assignments'][key]={'category':entry['category'],'path':entry['path']}
            render_navigation(root,index,memberships)
            atomic(root/'work/index.json',index)
            set_index=read(root/'sets/index.json')
            set_index['workspace_index']='work/index.json'
            set_index['workspace_categories']=SETS
            atomic(root/'sets/index.json',set_index)
            receipt=dict(report,completed=True,rewritten_implementation_files=rewritten,operational_changes=changes,
                         sources_unchanged=True,native_executions=0,recording_copies=0,
                         unsupported_historical_sources=unsupported_sources,
                         source_hashes=inputs,index_sha256=sha(root/'work/index.json'))
            atomic(root/'state/workspace-migration.json',receipt)
            return receipt
        finally:
            journal.close()


def freeze_campaign_resources(root,campaigns):
    """Retain the required executable, without copying its entire build cache."""
    resources={}
    for run in campaigns:
        source=root/'work'/run/'inputs/validator-core/.lake/build/bin/adapterCheck'
        if not source.is_file(): continue
        digest=sha(source)
        target=root/'inputs/adapters/validators'/digest/'adapterCheck'
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
        if sha(target)!=digest: raise ValueError('Frozen decoder checksum mismatch')
        resources[run]={'validator':str(target.relative_to(root)),'sha256':digest}
    return resources


def render_navigation(root,index,memberships):
    from recording_readmes import RecordingReadmes
    with_readmes = RecordingReadmes(root, memberships)
    try:
        return _render_navigation(root, index, memberships, with_readmes)
    finally:
        with_readmes.close()


def _render_navigation(root,index,memberships,recording_docs):
    grouped={}
    for entry in index['entries']:
        grouped.setdefault(entry['path'],[]).append(entry)
    for category in CATEGORIES:
        folder=root/'work'/category;folder.mkdir(parents=True,exist_ok=True)
        rows=['# '+category+' workspaces','', 'Generated navigation; set scopes and selections own coverage and recording membership.','',
              '| Cell | Law | Existing recordings | Implementation |','| --- | --- | ---: | --- |']
        demo_recorded=[];demo_planned=[]
        if category=='demo':
            accepted={m['recording_id']:m for name in ('demo-train','demo-test') for m in memberships.get(name,[]) if m.get('status','accepted')=='accepted'}
            planned_laws=set(read(root/'sets/demo-train/scope.json')['law_ids'])
            represented={m['law_id'] for m in accepted.values()}
            rows=['# Demo video review','',
                  str(len(accepted))+' accepted videos; '+str(len(represented & planned_laws))+'/'+str(len(planned_laws))+' demo laws represented. '
                  'Representation means at least one accepted recording, not complete statutory coverage or a resolved legal judgment.','',
                  'Open a cell/law README for the law text and tables grouped by comparison, with video links, test settings, counterparts, judgment calls and recorded labels.','',
                  '## Recorded assignments','',
                  '| Cell | Law / comparison tables | Accepted videos |','| --- | --- | ---: |']
        for path,entries in sorted(grouped.items()):
            e=entries[0]
            if e['category']!=category: continue
            ids={rid for item in entries for rid in item['recording_ids']}
            sources=sorted({s for item in entries for s in item['sources']})
            shared=sorted({s for item in entries for s in item['shared_sources']})
            dest=root/path;dest.mkdir(parents=True,exist_ok=True)
            text=['# '+e['cell_id']+' / '+e['law_id'],'',
                  'Actors: '+', '.join(sorted({item['actor'] for item in entries})), '',
                  'Existing recording references: '+str(len(ids))+'. Presence does not establish reviewed coverage completion.', '']
            if category=='demo':
                text += recording_docs.section(entries,ids,dest)
            text += ['## Implementation and history','']
            for source in sources+shared:
                relative=os.path.relpath(root/source,dest)
                text.append('- ['+Path(source).name+']('+relative+'/)'+(' (shared)' if source in shared else ''))
            if not sources: text.append('No dedicated implementation copied yet; shared sources and scoped coverage may be available.')
            text += ['', '## Sets and coverage','']
            set_ids=sorted({s for item in entries for s in item['set_ids']})
            for set_id in set_ids:
                base=root/'sets'/set_id
                text.append('- ['+set_id+' selection]('+os.path.relpath(base/'selection.json',dest)+') and [scope]('+os.path.relpath(base/'scope.json',dest)+').')
                for disposition in sorted((base/'coverage-dispositions').glob(e['cell_id']+'*'+e['law_id']+'*.json')):
                    data=read(disposition)
                    flags={k:v for k,v in data.items() if k in ('reviewed_cell_complete','reviewed_finite_assignment_complete','broader_statutory_coverage_complete')}
                    text.append('- [Coverage disposition: '+disposition.name+']('+os.path.relpath(disposition,dest)+'). '+json.dumps(flags))
            if category!='demo':
                text += ['', '## Recordings','']
                for rid in sorted(ids):
                    rel=os.path.relpath(root/'recordings'/rid,dest)
                    text.append('- ['+rid+']('+rel+'/metadata.json): [video]('+rel+'/video.webm), [trace]('+rel+'/trace.json).')
            text += ['', 'Keep new edits here or in a named implementation child. Freeze a new input/runtime revision before execution.',
                     'Copied scripts have relocated path literals; compile/check dependencies before use. Frozen receipts retain historical provenance.',
                     'See ../../../index.json for the workspace index. Old campaign directories are recovery sources, not active output destinations.','']
            atomic_text(dest/'README.md','\n'.join(text))
            if category=='demo':
                row='| '+e['cell_id']+' | ['+e['law_id']+']('+e['cell_id']+'/'+e['law_id']+'/README.md) | '+str(len(ids))+' |'
                (demo_recorded if ids else demo_planned).append(row)
            else:
                rows.append('| '+e['cell_id']+' | ['+e['law_id']+']('+e['cell_id']+'/'+e['law_id']+'/README.md) | '+str(len(ids))+' | '+('copied' if sources else ('shared' if shared else 'pending'))+' |')
        if category=='demo':
            rows += demo_recorded
            rows += ['', '## Planned assignments without recordings','',
                     'These additional cell/law assignments have no accepted video. The same law may already be represented above; these rows do not indicate lost recordings.','',
                     '| Cell | Law / planned workspace | Accepted videos |','| --- | --- | ---: |']+demo_planned
        if (folder/'HANDOFF.md').exists():
            rows += ['', '[Current handoff and pending ledger](HANDOFF.md).']
        rows += ['', 'Recovery directories and campaign administration are listed in [the workspace index](../index.json).','']
        atomic_text(folder/'README.md','\n'.join(rows))
    atomic_text(root/'work/README.md','# Active implementation work\n\n'+ '\n'.join('- ['+c+']('+c+'/README.md)' for c in CATEGORIES)+'\n\nUse [index.json](index.json) for implementation locations. Other historical campaign directories are preserved for recovery.\n')


def atomic_text(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.workspace-tmp')
    temp.write_text(text);temp.replace(path)


def refresh_workspaces(root=None, *, _lock_held=False):
    """Refresh derived navigation only; never recopy or change implementation."""
    root=(Path(root) if root is not None else OUTPUT_ROOT).resolve()
    with (nullcontext() if _lock_held else locked(root/'state/workspace-navigation.lock')):
        path=root/'work/index.json'
        index=read(path)
        if index.get('format')=='set-review-workspaces-v2':
            from lean_work import refresh
            return refresh(root)
        existing={(e['category'],e['cell_id'],e['law_id'],e['actor']):dict(e,set_ids=[],recording_ids=[]) for e in index['entries']}
        demo_laws=set(read(root/'sets/demo-train/scope.json')['law_ids'])
        memberships={};sources={}
        for set_id in SETS:
            base=root/'sets'/set_id
            scope=read(base/'scope.json');selection=read(base/'selection.json')
            memberships[set_id]=selection['members']
            for name in ('scope.json','selection.json'):
                sources[str((base/name).relative_to(root))]=sha(base/name)
            for item in scope.get('assignments',[])+selection['members']:
                category=category_for(scope['split'],item['law_id'],demo_laws)
                key=(category,item['cell_id'],item['law_id'],item['actor'])
                inherited=next((e for e in index['entries'] if (e['cell_id'],e['law_id'],e['actor'])==key[1:]),{})
                entry=existing.setdefault(key,dict(category=category,cell_id=item['cell_id'],law_id=item['law_id'],actor=item['actor'],
                                                  path=str(Path('work')/category/item['cell_id']/item['law_id']),
                                                  sources=list(inherited.get('sources',[])),shared_sources=list(inherited.get('shared_sources',[])),set_ids=[],recording_ids=[]))
                if set_id not in entry['set_ids']: entry['set_ids'].append(set_id)
                if item.get('recording_id') and item.get('status','accepted')=='accepted' and item['recording_id'] not in entry['recording_ids']:
                    entry['recording_ids'].append(item['recording_id'])
        index['historical_entries']=[e for e in existing.values() if not e['set_ids']]
        index['entries']=sorted((e for e in existing.values() if e['set_ids']),key=lambda e:e['path']+'|'+e['actor'])
        index['set_sources']=sources
        for entry in index['entries']:
            if entry['category']!='held-out':
                key='|'.join((entry['cell_id'],entry['law_id'],entry['actor']))
                index['assignments'][key]={'category':entry['category'],'path':entry['path']}
        render_navigation(root,index,memberships)
        atomic(path,index)
        return {'workspaces':len({e['path'] for e in index['entries']}),'implementation_files_changed':0,'recording_copies':0}
