"""Resolve and validate source-hashed alternatives for one exact case."""
import json
from pathlib import Path
from .common import read, sha, within
from .identity_preflight import validate as validate_identity

INVARIANT_CONFIG = ('cell_id', 'law_id', 'actor', 'selected_case_id',
                    'required_atoms', 'source_packets', 'rate_hz', 'duration_s',
                    'cameras', 'case')


def select(manifest, case_id, candidate_id='primary'):
    path = Path(manifest).resolve()
    entries = [entry for entry in read(path)['cases'] if entry['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact case identity')
    entry = entries[0]
    if candidate_id == 'primary':
        selected = {'id': 'primary', 'construction': entry['construction'],
                    'construction_sha256': entry['construction_sha256']}
    else:
        matches = [item for item in entry.get('candidates', []) if item.get('id') == candidate_id]
        if len(matches) != 1:
            raise ValueError('Unknown or duplicate candidate: '+candidate_id)
        selected = matches[0]
    source = within(path.parent, selected['construction'])
    if sha(source) != selected['construction_sha256']:
        raise ValueError('Candidate construction changed: '+candidate_id)
    construction = read(source)
    if construction.get('case_id') != case_id:
        raise ValueError('Candidate selected another case')
    return entry, selected, construction


def _config(construction):
    items = [item for item in construction['files'] if item['path'] == 'config.json']
    if len(items) != 1:
        raise ValueError('Candidate requires one config.json')
    return json.loads(items[0]['content'])


def validate(folder, entry, law_id, cell_id, required=False):
    folder = Path(folder)
    primary = read(within(folder, entry['construction']))
    validate_identity(primary, law_id, cell_id)
    risk = entry.get('candidate_risk')
    candidates = entry.get('candidates', [])
    if required:
        if not isinstance(risk, dict) or risk.get('status') not in ('none', 'physical') or not risk.get('reason'):
            raise ValueError('Every case needs a specific candidate risk assessment')
        if (risk['status'] == 'none' and candidates) or (risk['status'] == 'physical' and not candidates):
            raise ValueError('Fallbacks must match the declared physical risk')
    if not isinstance(candidates, list) or len(candidates) > 2:
        raise ValueError('At most two fallback candidates per case')
    ids = set()
    original = _config(primary)
    original_paths = {item['path'] for item in primary['files']}
    for candidate in candidates:
        ident = candidate.get('id')
        if ident not in ('fallback1', 'fallback2') or ident in ids:
            raise ValueError('Duplicate or unsupported candidate ID')
        ids.add(ident)
        trigger = candidate.get('trigger', {})
        if not isinstance(trigger, dict) or not all(trigger.get(key) for key in ('source', 'metric', 'failure_condition')):
            raise ValueError('Fallback needs a predeclared measurable failure trigger')
        if not candidate.get('changed_knobs') or not isinstance(candidate['changed_knobs'], list):
            raise ValueError('Fallback needs specific engineering changes')
        source = within(folder, candidate['construction'])
        if sha(source) != candidate.get('construction_sha256'):
            raise ValueError('Fallback construction changed')
        construction = read(source)
        if construction.get('case_id') != entry['case_id'] or construction.get('cell_id') != cell_id or construction.get('actor') != primary.get('actor'):
            raise ValueError('Fallback changed case, cell or actor')
        if construction.get('recording_description') != primary.get('recording_description'):
            raise ValueError('Fallback changed recording observations')
        if {item['path'] for item in construction['files']} != original_paths:
            raise ValueError('Fallback changed the implementation file inventory')
        changed = _config(construction)
        if any(changed.get(key) != original.get(key) for key in INVARIANT_CONFIG):
            raise ValueError('Fallback changed case or shared capture contract')
        validate_identity(construction, law_id, cell_id)
        if required:
            proof = candidate.get('offline', {})
            if (proof.get('exit_code') != 0 or proof.get('construction_sha256') != candidate['construction_sha256']
                    or not proof.get('command') or sha(within(folder, proof.get('log', ''))) != proof.get('log_sha256')):
                raise ValueError('Fallback lacks exact offline proof')
            spec = candidate.get('compatibility', {})
            if not all(spec.get(key) for key in ('receipt', 'sha256', 'log', 'negative_log')):
                raise ValueError('Fallback lacks positive/negative compatibility receipt')
            receipt = within(folder, spec['receipt'])
            if sha(receipt) != spec['sha256']:
                raise ValueError('Fallback compatibility receipt changed')
            result = read(receipt)
            if (result.get('format') != 'worker-package-compatibility-v2' or result.get('passed') is not True
                    or result.get('case_id') != entry['case_id'] or result.get('candidate_id') != ident
                    or result.get('construction_sha256') != candidate['construction_sha256']
                    or not {'selected_measurements', 'negative_case_source', 'lean_decoder', 'final_decode'}
                    <= set(result.get('checks', []))
                    or sha(within(folder, spec['log'])) != result.get('log_sha256')
                    or sha(within(folder, spec['negative_log'])) != result.get('negative_log_sha256')):
                raise ValueError('Fallback compatibility proof incomplete or changed')
    return {'case_id': entry['case_id'], 'fallbacks': sorted(ids)}
