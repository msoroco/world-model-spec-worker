"""Preserve source witness guidance with exact-case applicability, without false obligations."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];ids += [r['assignment_id'] for r in json.loads((ROOT/'work'/ids[0]/'additional-bindings.json').read_text())]
for aid in ids:
 folder=ROOT/'work'/aid;spec=json.loads((folder/'package-spec.json').read_text());plan=json.loads((folder/'case-plan.json').read_text());ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=folder/'assignment.json'
 a=json.loads(ap.read_text());requirement='Highway dedication and public-access source context, conventional vehicle/controller classification and exact fixed cell identity; factual legal scope conclusions remain separate.';source='assignment.witness.required_context; DEF-NRS-484A-080; DEF-NRS-484A-095; DEF-NRS-484A-320'
 spec['dispositions'][1].update(requirement=requirement,source=source,evidence_or_gap='Saved scope_context contains exact authored highway, vehicle blueprint, physical-control mechanism and fixed cell facts; actual public dedication, driver identity and legal vehicle qualification require independent factual review.')
 plan['requirement_dispositions'][1].update(requirement=requirement,source=source,evidence_or_gap=spec['dispositions'][1]['evidence_or_gap'])
 mapping=[]
 for text in a['witness']['required_context']:
  applicable=[]
  for case in spec['cases']:
   cfg=case.get('config',{});p=case['fixture']['case_observation.json'];keep=True;t=text.lower()
   if a['law_id']=='NRS-484B-413-2':
    district=cfg.get('district_class','business');course=cfg.get('course',a['cell']['maneuver'])
    if 'business' in t and district!='business':keep=False
    if 'right' in t and course!='right_turn':keep=False
    if '100' in t and cfg.get('signal_reference_ft',100)!=100:keep=False
    if ('loading' in t or 'freight' in t) and a['cell']['control']!='freight_loading_zone':keep=False
   if a['law_id']=='NRS-484B-227-1' and a['cell']['maneuver']=='left_turn' and 'u-turn' in t:keep=False
   if a['law_id'].startswith('NRS-484B-250'):
    if 'earlier' in t and p['entry_events']['other']['time_s']>=p['entry_events']['ego']['time_s']:keep=False
    if ('same' in t and 'intersection' in t) and p.get('other_crossing_id')=='second_roadway':keep=False
   if keep:applicable.append(aid+'__'+case['name'])
  mapping.append(dict(requirement=text,source='assignment.witness.required_context',case_ids=applicable,evidence_output_keys=['complete_statutory_observations','selected_scope_context'],applicability_reason='Applies only to listed exact cases with matching district, course, threshold and activation context; original guidance retained without overriding statutory branch alternatives.' if applicable else 'Base witness guidance is inapplicable to this supplemental fixed cell or negative qualification context; exact statutory law/definitions control these cases.'))
 plan['witness_requirement_applicability']=mapping
 (folder/'package-spec.json').write_text(json.dumps(spec,indent=2)+'\n');(folder/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 m=json.loads((folder/'execution-manifest.json').read_text())
 for entry in m['cases']:
  p=folder/entry['measurement_contract'];v=json.loads(p.read_text())
  for row in v['requirements']:
   if row['disposition_index']==1:row.update(requirement=requirement,source=source)
  p.write_text(json.dumps(v,indent=2)+'\n')
print('applicability corrected',len(ids),'packages')
