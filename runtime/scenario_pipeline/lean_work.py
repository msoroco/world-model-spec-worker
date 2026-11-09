"""Final-only review workspaces: one video, one lean trace, compact metadata."""
import hashlib
import json
import os
from pathlib import Path
import re

from recording_store import safe_name

SETS = ('demo-train', 'demo-test', 'full-train', 'full-test', 'held-out')
PARENTS = {'demo-train': 'full-train', 'demo-test': 'full-test'}
FORMAT = 'set-review-workspaces-v2'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def text(path, value):
    path=Path(path)
    if path.exists() and path.read_text()==value:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.review-tmp')
    temp.write_text(value)
    temp.replace(path)


def members(root):
    return {s:[m for m in read(root/'sets'/s/'selection.json')['members']
               if m.get('status','accepted')=='accepted'] for s in SETS}


def folder(member):
    return safe_name(member['cell_id'])+'--'+safe_name(member['law_id'])


def case_folder(member):
    rid=member['recording_id']
    if not re.fullmatch('[0-9a-f]{64}',rid):
        raise ValueError('Invalid recording ID')
    return safe_name(member['case_id'])+'--'+rid[:12]


def render(root, index, sets=SETS):
    from recording_readmes import cell, final_label
    work = root/'work'
    ms = members(root)
    top = ['# Review outputs', '', 'Demo recording folders link to their matching full-set folders. Edits through either path are shared.', '',
           '| Set | Accepted recordings |', '| --- | ---: |']
    for s in SETS:
        top.append('| ['+s+']('+s+'/README.md) | '+str(len(ms[s]))+' |')
        if s not in sets:continue
        lines = ['# '+s, '', 'Accepted review outputs. Settings are authored facts or controller requests; labels are the saved expected scenario labels. Acceptance does not establish exhaustive statutory coverage.', '',
                 '| Cell | Law and comparisons | Videos |', '| --- | --- | ---: |']
        if s != 'held-out' and (root/'inputs/shared/manifest.json').is_file():
            lines += ['[Shared acquisition manifest](manifest.json)', '']
        entries = [e for e in index['entries'] if e['set_id']==s]
        for e in entries:
            base = work/s/e['folder']
            model = read(root/'state/review_models'/s/(e['folder']+'.json'))
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
                    record = {'saved': {'expected_label': meta.get('expected_label'),
                                        'judgment_sweep': meta.get('judgment_sweep')},
                              'metadata': meta, 'judgments':r['judgments']}
                    peers = ', '.join(str(j) for j in range(1,len(rr)+1) if j!=i) or 'No accepted counterpart'
                    judgment=r.get('judgment_resolution') or '; '.join(r['judgments']) or 'None listed'
                    assets='[video]('+cf+'/video.webm) · [trace]('+cf+'/trace.json) · [metadata]('+cf+'/metadata.json)'
                    if meta.get('manifest_sha256'):
                        assets+=' · [manifest]('+cf+'/manifest.json)'
                    page.append('| '+str(i)+' | '+assets+' | '+cell(r['description']+((' (same reference video)' if not show_ids else ' (reused reference)') if r['reuse'] else ''))+' | '+peers+' | '+cell(judgment)+' | '+final_label(record)+' |')
                if show_ids:page += ['', 'Case IDs: '+'; '.join(str(i)+': `'+r['case_id']+'`' for i,r in enumerate(rr,1))+'.', '']
                else:page += ['']
            remaining=model.get('remaining_requirements_note','Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.')
            page += ['## Remaining requirements', '', remaining, '']
            text(base/'README.md', '\n'.join(page))
            shown={r['recording_id'] for g in model['comparisons'] for r in g['cases']} & set(by_rid)
            count=len(shown) if model.get('final_collection') else len(by_rid)
            lines.append('| '+e['cell_id']+' | ['+e['law_id']+']('+e['folder']+'/README.md) | '+str(count)+' |')
        text(work/s/'README.md', '\n'.join(lines)+'\n')
    text(work/'README.md', '\n'.join(top)+'\n')


def verify(root, work, index):
    if index.get('format')!=FORMAT:
        raise ValueError('Unsupported workspace layout')
    ms = members(root)
    expected_dirs = set(SETS)
    maintenance=work/'maintenance'
    if maintenance.is_dir():
        transfer=maintenance/'demo-entrance-associations-v3'
        archive=transfer/'entrance-associations-20-cases.zip'
        if ({p.name for p in maintenance.iterdir()}!={'demo-entrance-associations-v3'} or
                not transfer.is_dir() or
                {p.name for p in transfer.iterdir()}!={'entrance-associations-20-cases.zip'} or
                not archive.is_file() or archive.is_symlink()):
            raise ValueError('Unexpected work directories: maintenance')
        expected_dirs.add('maintenance')
    actual_dirs = {p.name for p in work.iterdir() if p.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError('Unexpected work directories: '+str(actual_dirs))
    if {p.name for p in work.iterdir() if p.is_file()} != {'README.md','index.json'}:
        raise ValueError('Unexpected work root files')
    links = 0; count = 0
    for s, rows in ms.items():
        expected_cells = {folder(m) for m in rows}
        if {p.name for p in (work/s).iterdir() if p.is_dir()} != expected_cells:
            raise ValueError('Unexpected cell/law directories: '+s)
        set_files = {'README.md'}
        if (root/'inputs/shared/manifest.json').is_file() and s != 'held-out':
            set_files.add('manifest.json')
            from shared_manifest import verify as verify_manifest
            verify_manifest(root, work/s, sha(root/'inputs/shared/manifest.json'))
        if {p.name for p in (work/s).iterdir() if p.is_file()} != set_files:
            raise ValueError('Unexpected set review files: '+s)
        for cell_name in expected_cells:
            cell_dir=work/s/cell_name
            expected_cases={case_folder(m) for m in rows if folder(m)==cell_name}
            if {p.name for p in cell_dir.iterdir() if p.name!='README.md'} != expected_cases:
                raise ValueError('Unexpected law review files: '+str(cell_dir))
            if not (root/'state/review_models'/s/(cell_name+'.json')).is_file():
                raise ValueError('Missing final review model: '+cell_name)
        for m in rows:
            d = work/s/folder(m)/case_folder(m)
            if s in PARENTS:
                target = work/PARENTS[s]/folder(m)/case_folder(m)
                if not d.is_symlink() or os.path.isabs(os.readlink(d)) or d.resolve()!=target.resolve():
                    raise ValueError('Wrong demo symlink: '+str(d))
                links += 1
            elif d.is_symlink():
                raise ValueError('Full-set case must be a real directory')
            meta=read(d/'metadata.json')
            expected_files={'video.webm','trace.json','metadata.json'}
            if meta.get('manifest_sha256'):
                if not re.fullmatch('[0-9a-f]{64}',meta['manifest_sha256']):
                    raise ValueError('Invalid final manifest hash: '+str(d))
                expected_files.add('manifest.json')
            if s not in PARENTS and {p.name for p in d.iterdir()} != expected_files:
                raise ValueError('Unexpected case review files: '+str(d))
            for name in ('video.webm', 'trace.json', 'metadata.json'):
                p = d/name
                if not p.is_file() or p.is_symlink():
                    raise ValueError('Missing or nonregular primary: '+str(p))
            if 'manifest.json' in expected_files:
                manifest=d/'manifest.json'
                if s != 'held-out' and (root/'inputs/shared/manifest.json').is_file():
                    from shared_manifest import verify as verify_manifest
                    verify_manifest(root, d, meta['manifest_sha256'])
                elif not manifest.is_file() or manifest.is_symlink() or sha(manifest)!=meta['manifest_sha256']:
                    raise ValueError('Final manifest hash differs: '+str(d))
            if meta.get('schema')!='final-review-recording-v1' or meta.get('recording_id')!=m['recording_id'] or meta.get('case_id')!=m['case_id'] or meta.get('law_id')!=m['law_id']:
                raise ValueError('Final review metadata identity differs: '+str(d))
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
    return {'accepted_memberships':count,'demo_directory_symlinks':links,'distinct_recordings':len({m['recording_id'] for rows in ms.values() for m in rows}),'broken_links':0,'auxiliary_directories_preserved':sorted(expected_dirs-set(SETS))}


def refresh(root, sets=SETS):
    root=Path(root);index=read(root/'work/index.json');ms=members(root)
    if index.get('format')!=FORMAT:
        raise ValueError('Unsupported workspace layout')
    expected={(s,m['recording_id']) for s,rows in ms.items() for m in rows}
    current={(e['set_id'],rid) for e in index['entries'] for rid in e['recording_ids']}
    if expected!=current:
        raise ValueError('Accepted membership changed; materialize new review outputs explicitly before refreshing')
    render(root,index,sets)
    return dict(verify(root,root/'work',index),implementation_files_changed=0,recording_copies=0)
