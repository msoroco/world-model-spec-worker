"""Three-region judgment coverage, independent of legal outcomes.

Callers supply source-bound, normalized measurements from declared windows.
Training includes accepted measurements and selected frozen targets; testing
includes accepted measured values only. Keys encode law, actor, judgment,
observable, unit and measurement definition, deliberately excluding cell.
"""
import math


def audit(training, testing):
    """Return witnesses and gaps for each training key; never infer measurements.

    Rows contain key (a stable string), value (finite number), and source
    (a source-bound recording or frozen-plan reference).
    """
    def group(rows):
        grouped = {}
        for row in rows:
            value = row['value']
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Finite judgment measurement required')
            if not row.get('source') or not isinstance(row.get('key'), str):
                raise ValueError('Judgment key and source reference required')
            grouped.setdefault(row['key'], []).append(dict(row))
        return grouped
    train, test = group(training), group(testing)
    results = []
    for key, rows in sorted(train.items()):
        low, high = min(r['value'] for r in rows), max(r['value'] for r in rows)
        values = test.get(key, [])
        regions = {
            'below': [r for r in values if r['value'] < low],
            'inside': [r for r in values if low < r['value'] < high],
            'above': [r for r in values if r['value'] > high],
        }
        results.append(dict(key=key, minimum=low, maximum=high,
                            training_sources=rows, witnesses=regions,
                            missing=[name for name, witnesses in regions.items() if not witnesses]))
    return {'passed': bool(results) and all(not r['missing'] for r in results),
            'ranges': results, 'missing_training_reference': not bool(results)}


def audit_set(root, set_id):
    """Discover frozen selected evidence; unsupported historical metadata is a gap.

    No range is reconstructed from a case name or controller request. A case
    must retain sweep_measurements and judgment_refs (or unresolved phrases).
    """
    import hashlib
    import json
    from pathlib import Path
    root = Path(root).resolve()
    sources, gaps = {}, []
    def read(path):
        data = path.read_bytes()
        sources[str(path.relative_to(root))] = hashlib.sha256(data).hexdigest()
        return json.loads(data)
    pair = {'demo-test':'demo-train','full-test':'full-train'}.get(set_id)
    if pair is None:
        scope_path=root/'sets'/set_id/'scope.json'
        pair=read(scope_path).get('training_set') if scope_path.exists() else None
    if not pair or Path(pair).name != pair:
        return dict(passed=False, gaps=['Missing explicit training counterpart'], ranges=[], sources=sources)
    def collect(sid, training):
        path=root/'sets'/sid/'selection.json'
        if not path.is_file():
            gaps.append('Missing selection: '+sid);return []
        selection=read(path);rows=[]
        if not selection.get('frozen'):gaps.append('Training/test selection is not frozen: '+sid)
        for member in selection.get('members',[]):
            if member.get('status') in ('unselected','superseded_unexecuted'):continue
            accepted=member.get('status')=='accepted'
            if not accepted and not training:continue
            if not accepted:
                # Pending training cases must name their immutable plan explicitly.
                reference=member.get('case_source')
                if not reference:
                    gaps.append('Selected training plan lacks case_source: '+member.get('case_id','?'));continue
                path=root/reference
                if root.resolve() not in path.resolve().parents:
                    raise ValueError('Training plan escapes output root')
                case=read(path);result={};published={}
            else:
                folder=root/'recordings'/member['recording_id']
                metadata=read(folder/'metadata.json');published=metadata.get('published_record',{})
                case={}
                for filename in ('case.json','config.json'):
                    candidate=folder/'evidence'/filename
                    if candidate.exists():
                        payload=read(candidate)
                        case=payload.get('case',payload)
                        if case.get('sweep_measurements'):break
                if member.get('judgment_metadata_recovery'):
                    if __package__:
                        from .judgment_case_metadata import resolve
                    else:
                        from judgment_case_metadata import resolve
                    case,recovery_sources=resolve(root,member,case,read)
                    sources.update(recovery_sources)
                result_path=folder/'evidence/result.json'
                result=read(result_path) if result_path.exists() else {}
                if published.get('judgment_sweep') or case.get('target_type')=='judgment_sweep':
                    trace=folder/'trace.json'
                    if not trace.exists():gaps.append('Missing canonical trace: '+member['recording_id'])
                    if result.get('diagnostic_fixture') or result.get('provenance_kind')=='synthetic_fixture':
                        gaps.append('Synthetic evidence cannot establish coverage: '+member['recording_id'])
                    if trace.exists():
                        with trace.open('rb') as stream:
                            checksum=hashlib.file_digest(stream,'sha256').hexdigest()
                        sources[str(trace.relative_to(root))]=checksum
                        if checksum!=metadata.get('trace_sha256'):gaps.append('Canonical trace hash differs: '+member['recording_id'])
            judgment=published.get('judgment_sweep') or case.get('target_type')=='judgment_sweep'
            if not judgment:continue
            refs=case.get('judgment_refs') or [{'phrase':p,'note':''} for p in case.get('unresolved_judgment_calls',[])]
            axes=case.get('sweep_measurements',[])
            if not refs or not axes:
                gaps.append('Missing judgment identity/measurement definition: '+member['case_id']);continue
            for axis in axes:
                observable=axis['observable'];unit=axis['unit'];measurement=axis['measurement']
                measured=result.get('realized_observables',{}).get(observable,{})
                if accepted and (measured.get('unit')!=unit or not isinstance(measured.get('value'),(int,float))):
                    gaps.append('Missing measured judgment value: '+member['case_id']+'/'+observable);continue
                values=[measured['value']] if accepted else []
                if training:
                    point=case.get('sweep_point',{})
                    if axis.get('variable',observable) in point:values.append(point[axis.get('variable',observable)])
                    elif not accepted:gaps.append('Frozen target lacks observable mapping: '+member['case_id']+'/'+observable)
                for ref in refs:
                    factor,canonical = {'km/h':(1/3.6,'m/s'),'km/hours':(1/3.6,'m/s'),'mph':(0.44704,'m/s'),'m/s':(1,'m/s'),'ft':(0.3048,'m'),'m':(1,'m')}.get(unit,(1,unit))
                    key=json.dumps([member['law_id'],member['actor'],ref,observable,canonical,measurement],sort_keys=True)
                    values_normalized=[v*factor for v in values]
                    rows.extend(dict(key=key,value=value,source=dict(set=sid,case_id=member['case_id'],recording_id=member.get('recording_id'))) for value in values_normalized)
        return rows
    training=collect(pair,True);testing=collect(set_id,False)
    report=audit(training,testing)
    report.update(set_id=set_id,training_set=pair,gaps=gaps,sources=sources)
    report['passed']=(report['passed'] or (not training and not testing)) and not gaps
    report['source_sha256']=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    return report


if __name__ == '__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Read-only judgment range audit')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--set',required=True)
    args=parser.parse_args()
    print(json.dumps(audit_set(args.root,args.set),indent=2))
