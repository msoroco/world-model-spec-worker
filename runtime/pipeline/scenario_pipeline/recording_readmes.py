"""Evidence-backed comparison tables for the demo viewing READMEs.

Read metadata and exact saved cases only. No evidence, labels, selections or jobs
are changed. A missing label stays missing; an accepted recording is not a verdict.
"""
import copy
import json
import os
from pathlib import Path
import re
import sqlite3


def read(path):
    return json.loads(Path(path).read_text())


def cell(value):
    """Escape one Markdown table cell, including multiline source text."""
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def words(value):
    return re.sub(r'\s+', ' ', re.sub(r'(?<=[A-Za-z])-(?=[A-Za-z])', ' ', str(value).replace('_', ' '))).strip()


def compact(value):
    if isinstance(value, str):
        return words(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(', ', ': '))


NAMES = {
    'commanded_following_gap': ('Following-gap request', 'm'),
    'commanded_speed': ('Cruise-speed request', 'm/s'),
    'commanded_approach_speed': ('Approach-speed request', 'm/s'),
    'commanded_leader_speed_drop': ('Lead-vehicle speed-reduction request', 'm/s'),
    'additional_vehicle_count': ('Additional vehicles', ''),
    'fog_setting': ('CARLA fog-density setting', ''),
    'precipitation_setting': ('CARLA precipitation setting', ''),
    'road_friction_setting': ('Road-friction setting', ''),
    'tire_friction_setting': ('Tire-friction setting', ''),
    'counterpart_position_request': ('Counterpart center-station request', 'm'),
    'post_stop_speed_request': ('Post-stop speed request', 'm/s'),
    'opposing_speed_request': ('Opposing-vehicle speed request', 'm/s'),
    'reference_front_margin_request': ('Front-to-reference margin request', 'm'),
    'commanded_signal_lead_distance': ('Signal lead-distance request', 'm'),
    'further_vehicle_count': ('Further opposing vehicles', ''),
}


def setting(name, assignment):
    value = assignment.get('value') if isinstance(assignment, dict) else assignment
    title, default_unit = NAMES.get(name, (words(name).capitalize(), ''))
    unit = assignment.get('unit', default_unit) if isinstance(assignment, dict) else default_unit
    if isinstance(value, dict):
        # Branch is the explicit physical comparison, not its bookkeeping paths.
        if value.get('branch') is not None:
            return title + ': ' + compact(value['branch'])
        return title + ': ' + compact(value)
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        value = '%g' % value
    return title + ': ' + compact(value) + (' ' + unit if unit else '')


def final_label(record):
    saved = record['saved']
    label = saved.get('expected_label', record['metadata'].get('expected_label'))
    if label is None:
        return 'Unresolved (no label assigned)' if record['judgments'] or saved.get('judgment_sweep') else 'Not assigned in saved metadata'
    labels = {'compliant': 'compliant', 'non_compliant': 'violation', 'violation': 'violation',
              'not_applicable': 'not applicable', 'not applicable': 'not applicable'}
    if label == 'inconclusive':
        if not record['judgments']:
            raise ValueError('An objective inconclusive label needs evidence review before publication')
        return 'Unresolved (judgment call)'
    return labels.get(label, words(label))


def differences(case):
    values = case.get('deliberate_differences', [])
    if isinstance(values, dict):
        return list(values)
    return [v.get('variable') if isinstance(v, dict) else v for v in values]


def group_id(case, saved):
    explicit = case.get('paired_probe_id') or case.get('sweep_id') or saved.get('group_id')
    if explicit:
        return explicit
    # Older saved metadata lacks comparison IDs. Retain the case stem and say
    # explicitly in the README that this is a display grouping, not equivalence.
    return re.sub(r'-(?:compliant-attempt|violating-attempt|compliant|violating|below|at|above|\d{4})$', '', case['case_id'])


class RecordingReadmes:
    def __init__(self, root, memberships, set_ids=('demo-train', 'demo-test')):
        self.root = Path(root)
        self.dbs = []
        self.runs = {}
        self.catalogs = []
        self.records = {}
        self.laws = {}
        self.revision_laws = {}
        self.templates = {}
        self.members = {}
        for set_id in set_ids:
            for member in memberships.get(set_id, []):
                if member.get('status', 'accepted') == 'accepted' and member.get('recording_id'):
                    self.members.setdefault(member['recording_id'], member)
        wanted_runs = {m.get('campaign') for m in self.members.values()}
        wanted_templates = {m['law_id']+'@'+m['actor'] for m in self.members.values()}
        for path in sorted((self.root/'state').glob('*.sqlite')):
            db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'runs', 'jobs'} <= tables:
                db.close()
                continue
            runs = db.execute('SELECT id,catalog_id FROM runs').fetchall()
            if not any(run in wanted_runs for run, _ in runs):
                db.close()
                continue
            self.dbs.append(db)
            for run, catalog in runs:
                self.runs[run] = (db, catalog, tables)
            if 'templates' in tables:
                marks=','.join('?' for _ in wanted_templates)
                query="SELECT template_id,json_extract(payload,'$.quote'),json_extract(payload,'$.structure.judgment_calls_needed') FROM templates WHERE template_id IN ("+marks+")"
                for key, quote, judgments in db.execute(query,tuple(wanted_templates)):
                    self.templates[key] = {'quote':quote,'structure':{'judgment_calls_needed':json.loads(judgments) if judgments else []}}
            if 'catalogs' in tables:
                for payload, in db.execute("SELECT json_extract(payload,'$.law_records') FROM catalogs"):
                    if payload:
                        self.catalogs.append(json.loads(payload))
            if 'input_revisions' in tables:
                row = db.execute("SELECT json_extract(payload,'$.catalog.law_records') FROM input_revisions ORDER BY rowid DESC LIMIT 1").fetchone()
                if row and row[0]:
                    self.catalogs.append(json.loads(row[0]))
        for rid, member in self.members.items():
            self.records[rid] = self.load_record(rid, member)
        for record in self.records.values():
            self.laws.setdefault(record['member']['law_id'], record['law'])

    def close(self):
        for db in self.dbs:
            db.close()

    def law(self, law):
        if law in self.laws and self.laws[law].get('text'):
            return self.laws[law]
        for catalog in reversed(self.catalogs):
            if isinstance(catalog, dict) and law in catalog:
                return catalog[law]
        for key, template in self.templates.items():
            if key.split('@')[0] == law and template.get('quote'):
                return {'id': law, 'text': template['quote']}
        return {'id': law, 'text': ''}

    def load_record(self, rid, member):
        metadata = read(self.root/'recordings'/rid/'metadata.json')
        saved = metadata.get('acceptance') or metadata.get('published_record') or {}
        identity = saved.get('provenance', {}).get('completion_binding', {})
        run = metadata.get('campaign', member.get('campaign'))
        case = {'case_id': metadata.get('case_id', member['case_id']),
                'variable_assignments': saved.get('variable_assignments', {})}
        revision = member.get('input_revision') or saved.get('provenance', {}).get('input_revision')
        law = None
        source = None
        if run in self.runs:
            db, _, tables = self.runs[run]
            jid = member.get('job_id') or metadata.get('job_id') or identity.get('job_id')
            if jid:
                row = db.execute("SELECT id,payload FROM jobs WHERE id=? AND stage='execution'", (jid,)).fetchone()
            else:
                row = db.execute("SELECT j.id,j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND j.stage='execution' AND j.entity=? ORDER BY j.id DESC LIMIT 1", (run, member['cell_id']+':'+case['case_id'])).fetchone()
            if row:
                payload = json.loads(row[1])
                candidate = payload.get('case', {})
                if candidate.get('case_id') != case['case_id']:
                    raise ValueError('Recording/case identity mismatch: '+rid)
                case = candidate
                source = 'Saved execution job '+str(row[0])
                revision = payload.get('input_revision', revision)
            if revision and 'input_revisions' in tables:
                # SQL extracts just the needed law from the frozen revision.
                path = '$.catalog.law_records."'+member['law_id']+'"'
                key = (run, revision, member['law_id'])
                if key not in self.revision_laws:
                    row = db.execute('SELECT json_extract(payload,?) FROM input_revisions WHERE run_id=? AND id=?', (path, run, revision)).fetchone()
                    self.revision_laws[key] = json.loads(row[0]) if row and row[0] else None
                law = self.revision_laws[key]
        template = self.templates.get(member['law_id']+'@'+member['actor'], {})
        judgments = case.get('unresolved_judgment_calls', [])
        if not judgments:
            judgments = [j['phrase'] for j in template.get('structure', {}).get('judgment_calls_needed', [])]
        judgments = [j.get('phrase', str(j)) if isinstance(j, dict) else j for j in judgments]
        # Accepted saved assignments can contain audited corrections to old aliases.
        assignments = dict(case.get('variable_assignments', {}))
        assignments.update(saved.get('variable_assignments', {}))
        case = dict(case, variable_assignments=assignments)
        return {'rid': rid, 'member': member, 'metadata': metadata, 'saved': saved,
                'case': case, 'law': law or self.law(member['law_id']),
                'judgments': sorted(set(judgments)), 'source': source or 'Saved recording metadata',
                'group': group_id(case, saved), 'reuse': None}

    def groups(self, records, dest):
        groups = {}
        for record in records:
            groups.setdefault(record['group'], []).append(record)
        # Retained explicit logical reuse receipts, at bounded comparison paths.
        # Do not infer equivalence from matching values or silently reuse a video.
        paths = [Path(dest)]
        index = read(self.root/'work/index.json') if (self.root/'work/index.json').exists() else {}
        for entry in index.get('entries', []):
            if entry.get('path') == str(Path(dest).relative_to(self.root)):
                paths += [self.root/p for p in entry.get('sources', [])]
        receipts = set()
        selections = set()
        for path in paths:
            receipts.update(path.glob('implementation-v*/comparisons/*/*reuse*.json'))
            receipts.update(path.glob('comparisons/*/*reuse*.json'))
            selections.update(path.glob('comparisons*/*/physical-comparison-selection.json'))
        by_case = {r['case']['case_id']: r for r in records}
        for path in sorted(selections):
            selection = read(path)
            planned = set(selection.get('planned_points', []))
            matches = [g for g, rows in groups.items() if any(r['case']['case_id'] in planned for r in rows)]
            if len(matches) != 1:
                continue
            rows = groups[matches[0]]
            for reference in selection.get('existing_original_references', []):
                original = by_case.get(reference.get('case_id'))
                if original and original['rid'] not in {r['rid'] for r in rows}:
                    reused = copy.deepcopy(original)
                    reused['reuse'] = path
                    reused['case']['deliberate_differences'] = differences(rows[0]['case'])
                    rows.append(reused)
        for path in sorted(receipts):
            receipt = read(path)
            if not receipt.get('passed') or not receipt.get('recording_id') or not receipt.get('logical_case_id'):
                continue
            rid = receipt['recording_id']
            if rid not in {r['rid'] for r in records}:
                continue
            logical = receipt['logical_case_id']
            # Bind to the destination comparison by its saved case ID stem.
            matches = [g for g, rows in groups.items() if any(re.sub(r'-\d{4}$', '', r['case']['case_id']) == re.sub(r'-\d{4}$', '', logical) for r in rows)]
            if len(matches) != 1:
                continue
            rows = groups[matches[0]]
            if rid in {r['rid'] for r in rows}:
                continue
            reused = copy.deepcopy(self.records[rid])
            reused['reuse'] = path
            reused['case']['case_id'] = logical
            reused['case']['deliberate_differences'] = differences(rows[0]['case'])
            # Exact logical case assignments are in the retained ordinary cases.
            for candidate in sorted(path.parent.glob('*cases*.json')):
                data = read(candidate)
                cases = data if isinstance(data, list) else data.get('cases', [])
                match = next((c for c in cases if c.get('case_id') == logical), None)
                if match:
                    reused['case'] = match
                    break
            reused['logical_encoding'] = receipt.get('logical_engineering_encoding', {})
            reused['reuse_physical'] = receipt.get('physical_configuration', {})
            rows.append(reused)
        return groups

    def section(self, entries, ids, dest):
        law_id = entries[0]['law_id']
        law = self.law(law_id)
        lines = ['## Law', '']
        if law.get('title'):
            lines += ['**'+law_id+' — '+law['title']+'**', '']
        else:
            lines += ['**'+law_id+'**', '']
        if law.get('text'):
            lines += ['> '+line for line in law['text'].splitlines()]
            lines += ['', 'Law text is the saved dataset source; these tables do not evaluate the statute.', '']
        else:
            lines += ['Law text is unavailable in the saved navigation sources.', '']
        records = [self.records[rid] for rid in sorted(ids) if rid in self.records]
        lines += ['## Recording comparisons', '']
        if not records:
            lines += ['No accepted demo recording is registered for this cell/law assignment. This is a planned workspace, not a missing video for every assignment of this law.', '']
            return lines
        lines += ['Each table groups cases from the same saved comparison. **Settings are authored facts or controller requests, not measured outcomes.** '
                  'The recorded label is the saved expected scenario label. “Accepted” describes the video/trace evidence; unresolved judgments remain unresolved.', '',
                  'Video links open the full recording. Metadata links retain the complete case identity and provenance. Simulator weather/friction settings are not legal thresholds.', '']
        for group, rows in sorted(self.groups(records, dest).items()):
            rows.sort(key=lambda r: r['case']['case_id'])
            names = sorted({n for r in rows for n in differences(r['case']) if n})
            if not names:
                names = varying_assignments(rows)
            title = comparison_title(group)
            lines += ['### '+title, '', 'Comparison ID: `'+group+'`.', '']
            if not any(r['case'].get('paired_probe_id') or r['case'].get('sweep_id') or r['saved'].get('group_id') for r in rows):
                lines += ['Older metadata has no explicit comparison ID; this viewing group uses the shared case-name stem and does not assert configuration equivalence.', '']
            if names:
                lines += ['Compare: '+', '.join(NAMES.get(n, (words(n), ''))[0] for n in names)+'.', '']
            judgments = sorted({j for r in rows for j in r['judgments']})
            judge = '; '.join('“'+words(j)+'”' for j in judgments) or 'No unresolved judgment listed for this comparison'
            lines += ['| Case | Video / metadata | Test setting or branch | Compared against | Judgment call | Recorded label |',
                      '| --- | --- | --- | --- | --- | --- |']
            for i, record in enumerate(rows, 1):
                rid = record['rid']
                rel = os.path.relpath(self.root/'recordings'/rid, dest)
                peer_ids = [str(j) for j in range(1, len(rows)+1) if j != i]
                peers = ', '.join(peer_ids) or 'No accepted counterpart in this workspace'
                video = '[Video '+rid[:8]+']('+rel+'/video.webm) · [metadata]('+rel+'/metadata.json) · [trace]('+rel+'/trace.json)'
                description = describe(record, names, rows)
                if record['reuse']:
                    description += ' (explicitly reused original; [reuse receipt]('+os.path.relpath(record['reuse'], dest)+'))'
                lines += ['| '+str(i)+' | '+video+' | '+cell(description)+' | '+(('Case ' if len(peer_ids)==1 else 'Cases ')+peers+' in this table' if len(rows)>1 else peers)+' | '+cell(judge)+' | '+final_label(record)+' |']
            lines += ['', 'Case identities: '+ '; '.join(str(i)+': `'+r['case']['case_id']+'`' for i, r in enumerate(rows, 1))+'.', '']
        return lines


def varying_assignments(rows):
    names = sorted({n for r in rows for n, a in r['case'].get('variable_assignments', {}).items() if a.get('kind') != 'subject_behavior'})
    return [n for n in names if len({json.dumps(r['case'].get('variable_assignments', {}).get(n, {}).get('value'), sort_keys=True) for r in rows}) > 1]


def comparison_title(group):
    suffix = re.sub(r'^C\d+[-_](?:\d+[A-Za-z]*[-_]\d+[A-Za-z]*[-_])?', '', group)
    suffix = re.sub(r'[-_]v\d+(?:[-_].*)?$', '', suffix)
    return words(suffix).capitalize()


def describe(record, names, rows):
    case = record['case']
    assignments = case.get('variable_assignments', {})
    details = []
    for name in names:
        if name in assignments:
            value = assignments[name]
            if isinstance(value.get('value'), dict):
                if value['value'].get('branch') is not None:
                    details.append(setting(name, value))
                    continue
                leaves = varying_leaves(name, rows)
                if leaves:
                    details += [setting(n, {'value': v}) for n, v in leaves_for(value['value'], name) if n in leaves]
                    continue
            details.append(setting(name, value))
    if record.get('reuse') and not details:
        # Preserve the logical encoding without attributing another case's
        # changed request to this immutable source original.
        encoding = record.get('logical_encoding')
        if encoding:
            action = encoding.get('physical_stop_mode')
            if action:
                return 'Reference original; action: '+words(action)
            return 'Reference original from '+record['member']['case_id']
        return 'Reference original from '+record['member']['case_id']
    if details:
        return '; '.join(details)
    probe = case.get('probe', {})
    if probe.get('target_value_or_branch') is not None:
        return compact(probe['target_value_or_branch'])
    return words(case['case_id'])


def leaves_for(value, prefix):
    if isinstance(value, dict):
        for key, child in sorted(value.items()):
            yield from leaves_for(child, prefix+'.'+key)
    else:
        yield prefix, value


def varying_leaves(name, rows):
    maps = [dict(leaves_for(r['case'].get('variable_assignments', {}).get(name, {}).get('value'), name)) for r in rows]
    names = {n for m in maps for n in m}
    # Bookkeeping and prose are retained in metadata, not confused with the
    # physical variable. Numeric/branch/boolean differences remain visible.
    skip = ('source', 'path', 'provenance', 'note', 'rationale', 'status', 'receipt', 'sha256')
    return {n for n in names if not any(s in n.split('.') for s in skip) and len({json.dumps(m.get(n), sort_keys=True) for m in maps}) > 1}
