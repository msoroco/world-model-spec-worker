"""Lossless interface normalization of retained construction descriptions."""
import shlex


def normalize_entrypoint(result):
    value=result.get('entrypoint')
    if not isinstance(value,dict):return
    files={f['path']for f in result.get('files',[])}
    path=value.get('file')
    if path is None:
        argv=shlex.split(value.get('command',''))
        candidates=[a for a in argv if a in files and a.endswith('.py')]
        if len(candidates)==1:path=candidates[0]
    if not isinstance(path,str) or path not in files or not path.endswith('.py'):
        raise ValueError('Construction entrypoint must identify one supplied Python file')
    result.setdefault('construction_contract_normalizations',[]).append({
        'field':'entrypoint','source':value,'canonical':path,
        'scope':'Only the file reference; readiness and diagnostics remain unchanged'})
    result['entrypoint']=path


def required_capture_atoms(bindings, templates, case):
    """Use target-law primitive observations retained from the pinned summaries.

    Derived drv.* concepts stay in source contracts and mandatory recording
    channels; they are not aliases for primitive entities or new Core fields.
    """
    active = {r['template_id'] for r in bindings.get('law_refs', [])}
    target=case.get('target_law_id')
    atoms = {o['atom'] for t in templates if t.get('template_id') in active and (target is None or t.get('law_id')==target)
             for o in t.get('structure', {}).get('required_observations', []) + t.get('source_required_observations', [])
             if isinstance(o, dict) and o.get('atom') and o['atom'].split('.',1)[0] in ('ru','kin','st','dev','sig','env','rel')}
    channels = case.get('recording_description', {}).get('channels', [])
    if any(c.get('name') in ('st.sight_distance', 'sight_distance') for c in channels):
        atoms.add('st.sight_distance')
    return sorted(atoms)
