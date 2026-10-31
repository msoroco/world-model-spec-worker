"""Production grouping and provenance, without autoformalization usage tracking."""
import hashlib
import json
from collections import Counter
from pathlib import Path


def law_family(law):
    parts=law.split('-')
    length=4 if parts[0]=='LVMC' else 3
    return '-'.join(parts[:length])


def metadata(record, catalog_cell=None):
    case=record['definition'];cell=catalog_cell or {}
    assignments=case.get('variable_assignments',{})
    facts={'layout':cell.get('layout'),'maneuver':cell.get('maneuver'),'control':cell.get('control')}
    comparison=case.get('paired_probe_id') or case.get('sweep_id') or case['target_law_id']
    family=hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()[:16]
    expected=record.get('recomputed_expectation',{})
    adapter_root=Path(record['trace_source']).parent if record.get('trace_source')else None
    capability=json.loads((adapter_root/'manifest.json').read_text())if adapter_root and (adapter_root/'manifest.json').exists()else None
    report=json.loads((adapter_root/'adapter_report.json').read_text())if adapter_root and (adapter_root/'adapter_report.json').exists()else {}
    return {'observation_capabilities':capability,'required_atom_coverage':report.get('atom_coverage'),
        'core_decoder_validation':report.get('decoder_validation'),'catalog_facts':facts,'law_family_id':law_family(case['target_law_id']),
        'law_family_rationale':'Parent statutory provision; no lexical merging or grouping by shared definitions',
        'cell_group_id':record['cell_id']+'@'+record.get('actor','motor_vehicle_driver'),
        'comparison_group_id':comparison,
        'scenario_family_id':case.get('scenario_family_id','catalog-'+family),
        'scenario_family_status':'declared' if case.get('scenario_family_id') else 'catalog_group_only',
        'scenario_family_rationale':'Use catalog cell/comparison groups conservatively; physical equivalence is not inferred from a shared town/controller',
        'original_execution_id':record.get('provenance',{}).get('source_run_id','')+':'+str(record.get('attempt_id')),
        'inconclusive_reasons':expected.get('inconclusive_reasons',[]),
        'reference_check':expected.get('reference_check'),
        'evaluation_status':expected.get('evaluation_status'),
        'intended_outcome':expected.get('intended_outcome'),
        'target_law_version':case.get('target_law_version'),
        'recording_description':case.get('recording_description'),
        'fixed_assumptions':expected.get('scene_assumptions',{}),
        'comparison_differences':case.get('deliberate_differences',[])}


def progress(manifest, milestone):
    cases=manifest.get('cases',[])
    groups=[g for g in manifest.get('groups',[]) if g.get('accepted_cases') or any(s.get('group_id')==g['group_id'] and s['status']!='unselected' and s['cell_id']==g['cell_id'] and s['actor']==g['actor'] for s in manifest.get('case_states',[]))]
    unfinished=[g for g in groups if not g.get('selected_complete')]
    inconclusive=[c for c in cases if c.get('expected_label')=='inconclusive']
    reasons=Counter(r for c in inconclusive for r in c.get('production_metadata',{}).get('inconclusive_reasons',[]))
    selected=manifest.get('selected_membership',[])
    identities={(c['cell_id'],c['actor'],c['case_id']) for c in cases}
    pending=[s for s in selected if (s['cell_id'],s['actor'],s['case_id']) not in identities]
    return {'accepted_pairs':len(cases),'labeled_pairs':sum(c.get('expected_label') in ('compliant','violation','not applicable') for c in cases),
        'inconclusive_pairs':len(inconclusive),'inconclusive_reasons':dict(reasons),
        'selected_groups':len(groups),'complete_selected_groups':len(groups)-len(unfinished),
        'unfinished_groups':unfinished,'unfinished_selected_members':pending,
        'milestone_target':milestone,'milestone_complete':bool(cases) and len(cases)>=milestone and not unfinished and not pending and manifest.get('complete',False)}
