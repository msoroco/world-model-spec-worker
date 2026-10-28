"""Bind selected witness requirements to executed diagnostic measurements."""
import ast
import json
from pathlib import Path
from .common import sha, within

TYPES={'number': (int,float), 'boolean': (bool,), 'object': (dict,), 'array': (list,), 'text': (str,)}
COMMON={'trace.jsonl','raw.mkv','video_frames.jsonl','capture/evidence.jsonl'}


def validate(contract, dispositions, analysis_code):
    if contract.get('format')!='worker-measurement-contract-v1':
        raise ValueError('Unknown measurement contract')
    selected={i for i,d in enumerate(dispositions) if d['status']=='selected_required'}
    rows=contract.get('requirements')
    if not isinstance(rows,list) or {r.get('disposition_index') for r in rows}!=selected or len(rows)!=len(selected):
        raise ValueError('Every selected requirement needs one case measurement')
    functions={node.name for node in ast.parse(analysis_code).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    outputs=set();inputs=set()
    for row in rows:
        if row.get('requirement')!=dispositions[row['disposition_index']]['requirement'] or row.get('source')!=dispositions[row['disposition_index']]['source']:
            raise ValueError('Measurement contract changed witness requirement')
        key=row.get('output_key')
        if not isinstance(key,str) or not key or key in outputs or key in ('source_complete','selected_branch_measurement','native_state'):
            raise ValueError('Measurement needs a distinct case-specific output key')
        outputs.add(key)
        if row.get('method') not in functions or row.get('value_type') not in TYPES or row.get('kind') not in ('measured','sourced_context'):
            raise ValueError('Measurement method/type missing from finalizer')
        sources=row.get('inputs')
        if not isinstance(sources,list) or not sources or any(not isinstance(s,str) or not s for s in sources):
            raise ValueError('Measurement needs concrete input files')
        inputs.update(sources)
    negative=contract.get('negative',{})
    removed=negative.get('remove')
    if not isinstance(removed,list) or len(removed)!=1 or removed[0] in COMMON or removed[0] not in inputs:
        raise ValueError('Negative fixture must remove one case-specific required input')
    if not isinstance(negative.get('error_contains'),str) or not negative['error_contains'].startswith('Missing required source: ') or removed[0] not in negative['error_contains']:
        raise ValueError('Negative fixture needs a specific expected error')
    return rows


def verify_report(contract, report, fixture):
    """Validate values and exact-file joins; physical truth remains unproved."""
    values=report.get('measurements')
    if not isinstance(values,dict):raise ValueError('Analysis report has no measurements')
    for row in contract['requirements']:
        key=row['output_key'];item=values.get(key)
        if not isinstance(item,dict) or item.get('method')!=row['method']:
            raise ValueError('Missing case-specific measurement: '+key)
        value=item.get('value')
        allowed=TYPES[row['value_type']]
        if value is None or not isinstance(value,allowed) or (row['value_type']=='number' and isinstance(value,bool)):
            raise ValueError('Measurement value has wrong type: '+key)
        if isinstance(value,(dict,list,str)) and not value:
            raise ValueError('Empty measurement value: '+key)
        if isinstance(value,str) and value.strip().lower() in ('pending','unverified','unknown','requires gpu','not measured'):
            raise ValueError('Placeholder measurement value: '+key)
        hashes=item.get('sources')
        if not isinstance(hashes,dict) or set(hashes)!=set(row['inputs']):
            raise ValueError('Measurement sources differ: '+key)
        for relative,checksum in hashes.items():
            if sha(within(fixture,relative))!=checksum:
                raise ValueError('Measurement source hash differs: '+key)
    return {key:values[key] for key in (r['output_key'] for r in contract['requirements'])}
