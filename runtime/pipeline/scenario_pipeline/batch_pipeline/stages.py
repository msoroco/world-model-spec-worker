"""Generic stage contracts and dependency expansion; no pilot inputs."""
import json
from pathlib import Path
from .store import digest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {'relevance': 'law-relevance-mapping', 'relevance_batch': 'law-relevance-mapping', 'template': 'law-cell-bindings',
          'judgment_observables': 'law-judgment-observables', 'bindings': 'law-cell-bindings',
          'cases': 'scenario-coverage-cases', 'construction': 'carla-scenario-build'}
SEMANTIC_STAGES = tuple(SKILLS)


def skill(stage):
    return (ROOT/'skills'/SKILLS[stage]/'SKILL.md').read_text()


def run_info(store, run):
    # A coordinated edit can be committed by another connection while a long
    # campaign is running. SQLite data_version detects those commits without
    # repeatedly parsing the large unchanged run configuration.
    data_version=store.db.execute('PRAGMA data_version').fetchone()[0]
    cache = getattr(store, '_run_cache', {})
    if getattr(store,'_run_cache_data_version',None)!=data_version:
        cache={}
        store._run_cache=cache
        store._run_cache_data_version=data_version
    if run in cache:
        return cache[run]
    row = store.db.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone()
    if not row:
        raise ValueError('Unknown run '+run)
    result = dict(row)
    result['config'] = json.loads(result['config'])
    if result['config'].get('judgment_policy') != 'fixed_sweeps':
        raise ValueError('Old pipeline run is unsupported; use fresh state and a new run ID')
    cache[run] = result
    store._run_cache = cache
    return result


def catalog(store, run):
    info = run_info(store, run)
    cache=getattr(store,'_catalog_cache',{})
    if info['catalog_id'] not in cache:
        cache[info['catalog_id']]=json.loads(store.db.execute('SELECT payload FROM catalogs WHERE id=?',(info['catalog_id'],)).fetchone()[0])
        store._catalog_cache=cache
    return cache[info['catalog_id']]


def enqueue(store, run, stage, entity, actor, payload, dependencies=()):
    config = run_info(store, run)['config']
    revisions = {json.loads(store.job(dep)['payload']).get('input_revision')
                 for dep in dependencies}
    revisions.discard(None)
    explicit = payload.get('input_revision')
    if explicit:
        revisions.add(explicit)
    if len(revisions) > 1:
        raise ValueError('Cannot mix immutable input revisions in one job')
    if revisions:
        from .run_inputs import job_revision
        revision = next(iter(revisions))
        config = job_revision(store, run, revision)['config']
        payload = dict(payload, input_revision=revision)
    payload = dict(payload, model_config=config.get('model', {}))
    if config.get('run_inputs_version'):
        payload['run_inputs_version'] = config['run_inputs_version']
    version = digest([skill(stage), CONTRACTS[stage], 'fixed-sweeps', json.loads((ROOT/'data/canonical_parameter_aliases.json').read_text()) if stage in ('template', 'bindings', 'cases') else None]) if stage in SKILLS else 'recording-contract'
    ident = store.enqueue(run, stage, entity, actor, payload, version, dependencies)
    if stage == 'bindings':
        job = store.job(ident)
        if job['status'] == 'completed':
            consumed = store.artifact(job['artifact_id'])['provenance'].get('template_versions', {})
            current = {k: digest(store.get_template(k)) for k in payload['template_ids']}
            if consumed != current:
                # Shared observable requirements/template changed. Preserve the old job; create a fresh version.
                ident = store.enqueue(run, stage, entity, actor, dict(payload, template_versions=current), version, dependencies)
    return ident


def actors(cell):
    if cell.get('grounding') == 'grounded':
        return [a for a in cell.get('grounding_by_party', {}) if a != 'unspecified']
    return cell.get('candidate_ego_parties', []) if cell.get('actor_status') != 'actor_mismatch' else []


def input_context(store, run, job):
    payload = json.loads(job['payload'])
    deps = [store.artifact(r[0]) for r in store.db.execute('''SELECT j.artifact_id FROM dependencies d
             JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? ORDER BY j.id''', (job['id'],))]
    inputs = {'request': payload, 'dependencies': [d['payload'] for d in deps]}
    source = catalog(store, run)
    config = run_info(store, run)['config']
    revision = payload.get('input_revision')
    if revision:
        from .run_inputs import job_revision
        frozen = job_revision(store, run, revision)
        source, config = frozen['catalog'], frozen['config']
    allowed = set(config.get('law_scope', {}).get('records', source['law_records']))
    if job['stage'] in ('relevance', 'relevance_batch', 'template'):
        if job['stage'] in ('relevance','relevance_batch'):
            inputs['law_records'] = {k:v for k,v in source['law_records'].items() if k in allowed}
            inputs['law_analysis'] = {k:v for k,v in source.get('law_analysis', {}).items() if k in allowed}
            inputs['law_summaries'] = {k:v for k,v in config.get('summaries', {}).items() if k in allowed}
            if not inputs['law_summaries']:
                raise ValueError('Missing pre-extracted law summaries')
            if job['stage']=='relevance_batch':
                keys=set(payload['law_ids'])
                for field in ('law_records','law_analysis','law_summaries'):
                    inputs[field]={k:v for k,v in inputs[field].items() if k in keys}
        else:
            law = payload['law_id']
            if law not in allowed:
                raise ValueError('Law outside frozen run scope: '+law)
            inputs['law_record'] = source['law_records'][law]
            inputs['law_summary'] = config.get('summaries', {}).get(law)
            if inputs['law_summary'] is None:
                raise ValueError('Missing pre-extracted law structure: '+law)
    if job['stage'] in ('template', 'bindings', 'cases'):
        inputs['canonical_parameter_rules'] = json.loads((ROOT/'data/canonical_parameter_aliases.json').read_text())
    if job['stage'] in ('bindings', 'cases', 'construction'):
        keys = payload.get('template_ids', [])
        if job['stage'] == 'cases':
            binding = next(d['payload'] for d in deps if 'variable_parameters' in d['payload'])
            active = {r['template_id'] for r in binding['law_refs']}
            keys = [key for key in keys if key in active]
        inputs['templates'] = [store.get_template(k, payload.get('template_versions', {}).get(k)) for k in keys]
        if any(t is None for t in inputs['templates']):
            raise ValueError('Missing shared template version')
    if job['stage'] in ('cases', 'construction'):
        if config.get('fewshots'):
            from .run_inputs import stage_examples
            inputs['fewshots'] = stage_examples(config['fewshots'], job['stage'])
        inputs['judgment_completion_policy'] = config.get('judgment_completion_policy', {})
        resources = config.get('simulator_context')
        inventory = payload.get('simulator_inventory')
        if job['stage'] == 'construction' and inventory is None:
            parent = next((d for d in deps if 'cases' in d['payload']), None)
            if parent:
                parent_request = json.loads(store.db.execute('SELECT payload FROM jobs WHERE id=?',
                                                            (parent['job_id'],)).fetchone()[0])
                inventory = parent_request.get('simulator_inventory')
        if inventory is not None:
            resources = dict(resources or {}, verified_inventory=inventory)
        if not resources and job['stage'] == 'construction':
            raise ValueError('Missing simulator resource context; configure it before selecting simulation')
        inputs['simulator_context'] = resources
    if job['stage'] == 'construction':
        # The original case, its complete bindings and law structures travel together.
        cases_job = next(d['job_id'] for d in deps if 'cases' in d['payload'])
        parent = store.db.execute("SELECT j.artifact_id FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? AND j.stage='bindings'", (cases_job,)).fetchone()
        inputs['bindings'] = store.artifact(parent[0])['payload']
        from .construction_contract import required_capture_atoms
        requirements = dict(inputs['simulator_context'].get('capture_requirements', {}))
        requirements['required_atoms'] = required_capture_atoms(inputs['bindings'], inputs['templates'], payload['case'])
        inputs['simulator_context'] = dict(inputs['simulator_context'], capture_requirements=requirements)
        from .construction_reuse import group_context
        group_cases = next(d['payload']['cases'] for d in deps if 'cases' in d['payload'])
        inputs['construction_group'] = group_context(payload, group_cases)
        group = payload['case'].get('paired_probe_id') or payload['case'].get('sweep_id')
        if group:
            for sibling in store.db.execute("SELECT j.artifact_id,j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='construction' AND j.actor=? AND j.status='completed' ORDER BY j.id DESC",
                                            (run, job['actor'])):
                request = json.loads(sibling['payload'])
                if request['cell']['cell_id'] == payload['cell']['cell_id'] and (request['case'].get('paired_probe_id') or request['case'].get('sweep_id')) == group and request['case'].get('target_law_id') == payload['case'].get('target_law_id'):
                    inputs['comparison_anchor'] = {'artifact_id': sibling['artifact_id'],
                                                  'case': request['case'],
                                                  'construction': store.artifact(sibling['artifact_id'])['payload']}
                    break
    if job['stage'] == 'judgment_observables':
        # Only this shared entry and law evidence: no cell inputs.
        inputs['template'] = store.get_template(payload['template_id'])
    reviews = [{'artifact_id': d['id'], 'review_status': d['review_status'], 'reviewed_at': d['reviewed_at']} for d in deps]
    provenance = {'input_catalog': run_info(store, run)['catalog_id'], 'job_input_version': job['cache_key'],
                  'dependencies': reviews, 'skill_version': digest(skill(job['stage'])) if job['stage'] in SKILLS else None,
                  'review_status': 'unreviewed'}
    if job['stage'] in ('relevance','relevance_batch'):
        provenance['catalog_provenance'] = payload.get('catalog_provenance', {})
        provenance['law_inputs'] = [{'law_id': k, 'text_version': digest(v),
            'annotation_version': digest(inputs['law_analysis'].get(k)),
            'annotation_review_status': inputs['law_analysis'].get(k, {}).get('review_status', 'unknown'),
            'summary_version': digest(inputs['law_summaries'].get(k)),
            'summary_review_status': inputs['law_summaries'].get(k, {}).get('review_status', 'unknown')}
            for k, v in inputs['law_records'].items()]
    if job['stage'] in ('template', 'judgment_observables'):
        provenance.pop('input_catalog', None)
        provenance['law_version'] = payload.get('law_version')
        provenance['summary_version'] = payload.get('summary_version')
        if job['stage'] == 'template':
            provenance['summary_review_status'] = inputs['law_summary'].get('review_status', 'unknown')
        if job['stage']=='judgment_observables':
            provenance['template_version'] = digest(inputs['template'])
    if 'templates' in inputs:
        provenance['template_versions'] = {t['template_id']: digest(t) for t in inputs['templates'] if t}
    if 'canonical_parameter_rules' in inputs:
        provenance['canonical_parameter_rules_version'] = digest(inputs['canonical_parameter_rules'])
    if 'simulator_context' in inputs:
        provenance['simulator_context_version'] = digest(inputs['simulator_context'])
    if revision:
        provenance['input_revision'] = revision
        provenance['input_catalog'] = digest(source)
    if config.get('run_inputs_version'):
        provenance['run_inputs_version'] = config['run_inputs_version']
    if 'comparison_anchor' in inputs:
        provenance['comparison_anchor_artifact'] = inputs['comparison_anchor']['artifact_id']
    if 'templates' in inputs and any(t['law_id'] not in allowed for t in inputs['templates']):
        raise ValueError('Template outside frozen run law scope')
    return inputs, provenance


CONTRACTS = {
'relevance': 'Return {cell_id, actor, status:"draft", relevant_laws:[{law_id,quote,applies_to:[actor],relevance_type,confidence,notes}], borderline_excluded:[{law_id,reason}]}. Review every provided summary and general duties. Do not infer context from possibility. Explicitly authored request.explicit_contexts are allowed as additional facts for this run; never infer other overlays.',
'template': 'Return one {template_id:"law_id@actor",law_id,actor,quote,structure:{law_id,activation:{condition,numeric_conditions:[]},obligation:{description,type,numeric_conditions:[]},exceptions:[{trigger,effect,replacement_obligation,source_clause}],timing:{description,numeric_conditions:[]},judgment_calls_needed:[{phrase,note}]},parameter_refs:[{name,kind,range_or_domain}]}. Build only the shared law structure from this law and summary. No cell-specific assumptions. Preserve exact exception clauses and canonical measured variables. Every numeric_conditions item MUST use {variable,operator,value,unit}; never use parameter as its field name. obligation.type is must or must_not. Exceptions and judgment_calls_needed are lists of objects, never strings.',
'judgment_observables': 'Return {template_id,phrase,note,status:"draft",observable_requirements:{observables:[{name,unit,description}],context_inputs:[{name,unit,description}],sweep_dimensions:[{name,unit,description}],landmarks:[{name,description,source,verification_evidence}],recording_needs:[{name,unit,description}],limitations:[string]}}. Value-free law/actor requirements only. Never choose a bound, formula, legal meaning, surrogate rule, or numeric value. No cell data. Identify raw evidence useful to later predicates, without claiming intent is observable. Factual lookups remain world_setup. Verify cited landmark sources; landmarks define potential coverage anchors only.',
'bindings': 'Return {cell_id,actor,status:"draft",established_contexts:[],law_refs:[{template_id,binding_kind}],context_refs:[{template_id,missing_guards}],fixed_parameters:[{name,value,rationale}],variable_parameters:[{name,kind,range_or_domain,used_by_laws}]}. Cover every selected template exactly once. Do not let context_refs add base variables. Explicitly attached contexts may satisfy their guards; check actor and remaining activation separately. Unattached independent facts stay conditional. Deduplicate parameter names and use world_setup/subject_behavior/controller. When ego_speed is observed, include one scalar commanded_approach_speed controller target in m/s for physical sweeps, separate from trace-only ego_speed; include commanded_turn_path for the requested maneuver. These targets select no legal standard or value.',
'cases': 'Return {cell_id,actor,status:"draft",cases:[baseline and statutory/plain cases],sweep_specs:[spec]}. Use case_defaults:{variable_assignments:<full map of every bound variable>,recording_description:<full description>} once. Ordinary cases and complete sweep_specs provide only changed assignment entries; deterministic code materializes full maps and inherited recording descriptions. Each ordinary case MUST have {case_id,target_law_id:null for baseline or exact active law ID,target_type:baseline|boundary_probe|compliant_attempt|violating_attempt,rationale,variable_assignments:<overrides>,unresolved_judgment_calls:[]}. Non-baseline ordinary cases also require paired_probe_id,deliberate_differences:[variable names],probe:{primary_variable,comparison_or_standard,target_value_or_branch}; statutory probes also require probe.threshold_ref,operator,unit,test_value and epsilon_used. Never use alternate names for these fields. Keep notes concise and avoid repeating shared assignments or recording descriptions. Never output expanded judgment cases; deterministic code expands them. Every ordinary case needs recording_description and full variable_assignments; subject_behavior.value is null. Retain numeric below/at/above triples with threshold_ref, operator, unit, test_value and epsilon. Compliant_attempt/violating_attempt pairs require a plain rule or the explicit deterministic_branch contract below. A judgment law needs fixed physical sweep specs for every phrase; no judgment value or anticipated compliance label. Each spec: {sweep_id,target_law_id,judgment_refs:[{phrase,note}],status:"complete"|"incomplete",mode:"one_dimensional"|"joint",axes:[{variable,observable,unit,min,max,spacing,measurement:{method,time_window,statistic},range_rationale,spacing_rationale,feasibility_evidence}],landmarks:[{name,value,unit,source,verification_evidence,purpose:"coverage_landmark"}],rationale,variable_assignments,recording_description}. Incomplete specs instead need missing_inputs. Axes vary scalar controller targets or world_setup values, mapped to canonical physical observables. Supply documented physical feasibility and meaningful resolution, never a legal threshold. Prefer independent sweeps; justify joint grids. Do not adapt to later labeling or execution budget. Recording_description is {channels:[{name,unit,sampling_rate_hz,method,time_window,reference_frame,uncertainty}],context_inputs:[{name,unit,method}],limitations:[string]}. Include all active law observable requirements and relevant instance context; unsupported capability produces incomplete plans. Preserve one-law isolation, paired_probe_id/deliberate_differences, and full assignments. No declaration use or expected labels for actual judgment sweeps.',
'construction': 'Return {cell_id,actor,case_id,status:"draft",files:[{path,content}],entrypoint,mechanisms,measurement_plan,recording_description,static_checks,termination_rules}. Provide a standalone Python CARLA runner executable with --output-dir PATH and --host HOST --port PORT. It must handle termination signals and clean up owned actors/sensors/world settings without stopping another server. It must write result.json with measured_values, target_checks:[{target,requested,measured,method,tolerance,matched,physical_cause_confirmed,cause_evidence}], setup_confirmed,behavior_attempted,maneuver_completed,termination_reason,physical_failure_flags,trace_reference,video_references and video_frame_map_reference. Capture position/heading/speed and cameras during one run. Preserve the case recording_description exactly; for ordinary cases use its supplied description. result.json also needs recording_description, recording_evidence:[{name,unit,reference}], and realized_observables:{name:{value,unit,method,time_window,statistic,reference}}. Each recorded channel references a JSONL stream of {time_s,value} at the declared rate; context channels reference a JSON object keyed by name. Preserve all required raw observations, authored geometry, friction/weather inputs, participants, and context. A sweep summary must use its declared method/window/statistic and retain the raw stream. For sweep summaries use the case sweep_measurements definitions exactly and supply sample_window_s:[start,end] selecting actual saved samples; summary values must recompute from their raw streams. Record missing capability explicitly rather than fabricate data. Do not add sweep points or replay unchanged constructions to fill gaps. Diagnose and repair missing realization at the same frozen setting through the repair contract. Expected labels are computed downstream from recorded evidence; actual judgment sweeps stay unlabeled. Trace is JSONL with {frame,time_s,position:{x,y,z},heading_deg,speed_mps}; video frame map is JSONL with {video_frame (zero-based consecutive),carla_frame,time_s}, exactly one per saved trace sample/video frame. Record physical-cause evidence for each target, not just its number. No legal verdict. Do not start CARLA or run the case while constructing files. No pilot-specific imports. Use actual documented client APIs; expose static checks using --check without simulator connection.'}


CONTRACTS['relevance_batch']=CONTRACTS['relevance']

def prompt(stage, inputs):
    prompt_inputs=inputs
    instructions=CONTRACTS[stage]
    if stage=='construction':
        # The full cell case-plan artifact and every law template are retained
        # in SQLite/provenance, but repeating unrelated cases/templates in each
        # construction prompt creates enormous, redundant model inputs. The
        # exact selected case, its complete linked group, full bindings, and
        # full target-law templates remain present.
        from copy import deepcopy
        from .store import digest
        prompt_inputs=deepcopy(inputs)
        group=prompt_inputs.get('construction_group',{}).get('cases',[])
        target_laws={case.get('target_law_id') for case in group if case.get('target_law_id')}
        all_templates=prompt_inputs.get('templates',[])
        target_templates=[t for t in all_templates if t.get('law_id') in target_laws]
        if target_laws and target_laws <= {t.get('law_id') for t in target_templates}:
            prompt_inputs['templates']=target_templates
        else:
            target_templates=all_templates
        case_artifacts=[d for d in inputs.get('dependencies',[]) if isinstance(d,dict) and isinstance(d.get('cases'),list)]
        omitted_case_ids=sorted({case.get('case_id') for dep in case_artifacts for case in dep['cases']
                                 if case.get('case_id') not in {m.get('case_id') for m in group}})
        prompt_inputs['construction_context_compaction']={
            'policy':'selected_case_and_linked_group_v1',
            'full_case_plan_sha256':[digest(dep) for dep in case_artifacts],
            'omitted_unrelated_case_ids':omitted_case_ids,
            'omitted_template_ids':sorted(t.get('template_id') for t in all_templates
                                          if t not in target_templates and t.get('template_id')),
            'retained_target_law_ids':sorted(target_laws),
            'upstream_artifacts_retained_in_database':True,
        }
        prompt_inputs['dependencies']=[]
        instructions += (' The case plan and all cell-level law analysis remain preserved upstream. For this construction use the exact selected case, its complete linked comparison group, complete bindings, and complete template(s) for that group’s target law(s); do not infer or alter any case meaning.')
    return {'stage': stage, 'skill': skill(stage), 'instructions': instructions,
            'execution_policy': 'Autonomous workflow: no human approval gate. Judgment meanings remain unknown. Produce fixed physical coverage and recorded evidence only. Never claim human approval. Preserve provenance; block only genuinely missing/invalid inputs. Output JSON, not prose. Do not execute a simulation in a semantic job.',
            'inputs': prompt_inputs}


CONTRACTS['construction'] += ' If comparison_anchor is supplied, reuse its exact runner, map, props, camera and controller implementation; change only the case-specific scalar assignments and identifiers named in deliberate_differences. Return complete files. Do not independently redesign a linked comparison. Resource inspection comes from inline verified_inventory when supplied; no worker shell is required.'
CONTRACTS['construction'] += ' The executor creates output-dir and materializes your files before launch: allow that existing directory, create only new capture/evidence files exclusively, and do not require another CLI flag for endpoint ownership. The executor has a dedicated CARLA resource lease. Your own config.json is preserved; executor construction metadata is construction.json. --check must remain offline. A nonzero exit after result.json is retained as an explicit physical/target failure; never replace observations with requested targets.'


def check_parameter_names(parameters, rules):
    names = [v['name'] for v in parameters]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate canonical variables')
    for name in names:
        if name in rules.get('aliases', {}):
            raise ValueError('Use canonical parameter '+rules['aliases'][name]+' instead of '+name)
        if name in rules.get('derived_comparisons', []):
            raise ValueError('Comparison is not an independent parameter: '+name)
        if name == 'kin.velocity':
            raise ValueError('Split velocity observation into canonical speed/trajectory and participant quantities')


def validate(stage, result, inputs):
    if not isinstance(result, dict):
        raise ValueError('Stage result must be an object')
    from .validation import no_interpretations,strip_null_prohibited_fields
    removed=strip_null_prohibited_fields(result)
    if removed:
        result.setdefault('pipeline_normalizations',[]).append({
            'rule':'omit_null_prohibited_fields_v1','paths':removed})
    no_interpretations(result)
    request = inputs['request']
    if result.get('status', 'draft') != 'draft':
        raise ValueError('New semantic artifacts must remain draft')
    if stage in ('relevance','relevance_batch','bindings','cases','construction'):
        if result.get('cell_id') != request['cell']['cell_id'] or result.get('actor') != request['actor']:
            raise ValueError('Cell or actor mismatch')
    if stage in ('relevance','relevance_batch'):
        if not isinstance(result.get('relevant_laws'), list) or 'borderline_excluded' not in result:
            raise ValueError('Missing relevant laws or exclusions')
        seen = set()
        for law in result['relevant_laws']:
            key = law['law_id']
            if key in seen or key not in inputs['law_records']:
                raise ValueError('Duplicate/unknown relevant law')
            seen.add(key)
            if not law.get('quote') or law['quote'] not in inputs['law_records'][key]['text']:
                raise ValueError('Supporting quote is not exact law text')
            if law['applies_to'] != [request['actor']]:
                raise ValueError('Law must be checked for this actor independently')
            if law.get('confidence') not in ('high','medium','low'):
                raise ValueError('Invalid relevance confidence')
    elif stage == 'template':
        if result.get('law_id')!=request['law_id'] or result.get('actor')!=request['actor']:
            raise ValueError('Template law/actor mismatch')
        if result.get('template_id') != request['law_id']+'@'+request['actor']:
            raise ValueError('Invalid template identity')
        if not result.get('quote') or result['quote'] not in inputs['law_record']['text']:
            raise ValueError('Template quote is not exact')
        structure = result.get('structure')
        if not isinstance(structure, dict):
            raise ValueError('Template structure must be an object')
        for key in ('activation','obligation','exceptions','timing','judgment_calls_needed'):
            if key not in structure:
                raise ValueError('Missing template structure '+key)
        def check_numeric(value):
            if isinstance(value, dict):
                if 'operator' in value and 'value' in value:
                    if not {'variable', 'operator', 'value', 'unit'} <= value.keys():
                        raise ValueError('Numeric condition requires variable, operator, value, unit')
                for child in value.values():
                    check_numeric(child)
            elif isinstance(value, list):
                for child in value:
                    check_numeric(child)
        check_numeric(structure)
        for key in ('exceptions', 'judgment_calls_needed'):
            if not isinstance(structure[key], list) or any(not isinstance(item, dict) for item in structure[key]):
                raise ValueError('Template '+key+' must be a list of objects')
        for e in structure['exceptions']:
            if not e.get('source_clause') or e['source_clause'] not in inputs['law_record']['text']:
                raise ValueError('Exception clause is not exact')
        for j in structure['judgment_calls_needed']:
            if not j.get('phrase') or 'observable_requirements' in j:
                raise ValueError('Template writer flags phrases; observable worker supplies evidence requirements')
        if not isinstance(result.get('parameter_refs'), list):
            raise ValueError('Missing canonical parameter references')
        check_parameter_names(result['parameter_refs'], inputs.get('canonical_parameter_rules', {}))
    elif stage == 'judgment_observables':
        if (result.get('template_id'), result.get('phrase'), result.get('note', '')) != (request['template_id'], request['phrase'], request.get('note', '')):
            raise ValueError('Judgment identity mismatch')
        from .validation import observable_requirements
        observable_requirements(result.get('observable_requirements', {}))
    elif stage == 'bindings':
        expected = set(request['template_ids'])
        found = [r['template_id'] for k in ('law_refs','context_refs') for r in result[k]]
        if len(found) != len(set(found)) or set(found) != expected:
            raise ValueError('Bindings must account for every template exactly once')
        check_parameter_names(result['variable_parameters'], inputs.get('canonical_parameter_rules', {}))
        names = [v['name'] for v in result['variable_parameters']]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate canonical variables')
        for v in result['variable_parameters']:
            if v.get('kind',v.get('type')) not in ('world_setup','subject_behavior','controller'):
                raise ValueError('Invalid variable kind')
        if any(v['name'] == 'ego_speed' and v.get('kind', v.get('type')) == 'subject_behavior'
               for v in result['variable_parameters']) and not any(
                   v.get('kind', v.get('type')) == 'controller' and 'speed' in v['name']
                   for v in result['variable_parameters']):
            raise ValueError('Speed-observing bindings need an explicit speed controller target; actual ego_speed remains trace-only')
        active_citations = {r['template_id'] for r in result['law_refs']} | {r['template_id'].split('@')[0] for r in result['law_refs']}
        fixed_names = [p['name'] for p in result['fixed_parameters']]
        if len(fixed_names) != len(set(fixed_names)) or set(fixed_names) & set(names):
            raise ValueError('Fixed facts cannot also be variable parameters')
        for v in result['variable_parameters']:
            citations = set(v.get('used_by_laws', []))
            if not citations <= active_citations or not citations and v.get('kind', v.get('type')) != 'controller':
                raise ValueError('Base variable needs active-law support; conditional context cannot inflate it: '+v['name'])
        for r in result['context_refs']:
            if not r.get('missing_guards'):
                raise ValueError('Conditional law needs explicit missing context guards')
        for r in result['law_refs']:
            if r['binding_kind'] not in ('direct','general_duty'):
                raise ValueError('Unresolved context cannot be active')
    elif stage == 'cases':
        binding = next(d for d in inputs['dependencies'] if 'variable_parameters' in d)
        names = {v['name']:v.get('kind',v.get('type')) for v in binding['variable_parameters']}
        active = {r['template_id'].split('@')[0] for r in binding['law_refs']}
        ids, groups = set(), {}
        baseline = False
        for case in result['cases']:
            if case['case_id'] in ids:
                raise ValueError('Duplicate case id')
            ids.add(case['case_id'])
            baseline |= case['target_type'] == 'baseline'
            if case['target_type'] != 'baseline' and case['target_law_id'] not in active:
                raise ValueError('Case uses inactive law')
            assignments = case['variable_assignments']
            if set(assignments) != set(names):
                raise ValueError('Case '+case['case_id']+' variables: missing '+str(sorted(set(names)-set(assignments)))+
                                 '; extraneous '+str(sorted(set(assignments)-set(names))))
            for name, a in assignments.items():
                if a['kind'] != names[name] or (a['kind'] == 'subject_behavior' and a['value'] is not None):
                    raise ValueError('Incorrect variable kind or guaranteed behavior')
            if case.get('paired_probe_id'):
                groups.setdefault(case['paired_probe_id'], []).append(case)
        if not baseline:
            raise ValueError('Missing shared baseline')
        from .validation import coverage
        coverage(result['cases'], binding, inputs.get('templates', []), result.get('sweep_specs', []))
        from .validation import recording_description
        for case in result['cases']:
            requirements = [j['observable_requirements'] for t in inputs.get('templates', [])
                if t['law_id'] == case.get('target_law_id') for j in t['structure']['judgment_calls_needed']]
            recording_description(case.get('recording_description'), requirements)
        for group in groups.values():
            allowed = set()
            for case in group:
                differences = case.get('deliberate_differences', [])
                if isinstance(differences, dict):
                    allowed.update(differences)
                else:
                    allowed.update(d['variable'] if isinstance(d,dict) else d for d in differences)
            first = group[0]['variable_assignments']
            for case in group[1:]:
                for name in names:
                    if name not in allowed and case['variable_assignments'][name] != first[name]:
                        raise ValueError('Undeclared comparison difference: '+name)
    elif stage == 'construction':
        mechanism_status=result.get('mechanisms',{})
        mechanism_status=mechanism_status.get('construction_status') if isinstance(mechanism_status,dict) else None
        for readiness in (result.get('construction_status'),mechanism_status):
            if isinstance(readiness,str) and any(token in readiness.casefold() for token in ('blocked','failed','unsupported','missing_input')):
                raise ValueError('Construction not executable: '+readiness)
        if result.get('blocking_reasons'):
            raise ValueError('Construction not executable: '+str(result['blocking_reasons']))
        def failed_static_check(value):
            if isinstance(value,dict):
                for key in ('status','result','outcome'):
                    status=value.get(key)
                    if isinstance(status,str) and status.casefold().startswith(('failed','blocked','unsupported')):
                        return status
                for child in value.values():
                    failure=failed_static_check(child)
                    if failure:return failure
            elif isinstance(value,list):
                for child in value:
                    failure=failed_static_check(child)
                    if failure:return failure
            return None
        failure=failed_static_check(result.get('static_checks',[]))
        if failure:
            raise ValueError('Construction not executable: static check '+failure)
        from .validation import recording_description
        recording_description(result.get('recording_description'))
        if result['recording_description'] != request['case']['recording_description']:
            raise ValueError('Construction changes the frozen recording description')
        from pathlib import PurePosixPath
        if result.get('case_id') != request['case']['case_id']:
            raise ValueError('Construction case mismatch')
        files = result.get('files', [])
        paths = set()
        for f in files:
            p = PurePosixPath(f['path'])
            if p.is_absolute() or '..' in p.parts or str(p) in paths:
                raise ValueError('Unsafe/duplicate construction path')
            paths.add(str(p))
            if p.name == 'config.json':
                from intentions import validate_context
                configuration=json.loads(f['content'])
                validate_context(configuration.get('authored_test_context',{}), resolve_bindings=False)
            if p.suffix == '.py':
                compile(f['content'],str(p),'exec')
        from .construction_reuse import validate_contract
        validate_contract(result, inputs)
        from .repairs import validate_repair
        validate_repair(result,inputs['request'])
        if not isinstance(result.get('entrypoint'),str) or result.get('entrypoint') not in paths or not result.get('entrypoint', '').endswith('.py') or not result.get('measurement_plan') or not result.get('static_checks'):
            raise ValueError('Missing entrypoint or measurement/static checks')


def expand(store, run, job, result, artifact_id):
    stage, request = job['stage'], json.loads(job['payload'])
    if stage == 'relevance':
        source = catalog(store, run)
        config = run_info(store, run)['config']
        if request.get('input_revision'):
            from .run_inputs import job_revision
            frozen = job_revision(store, run, request['input_revision'])
            source, config = frozen['catalog'], frozen['config']
        summaries = config.get('summaries', {})
        ids, deps = [], [job['id']]
        for law in result['relevant_laws']:
            key = law['law_id']+'@'+job['actor']
            tid = enqueue(store,run,'template',key,job['actor'],
                {'law_id':law['law_id'],'actor':job['actor'],'law_version':digest(source['law_records'][law['law_id']]),
                 'summary_version':digest(summaries.get(law['law_id'])),
                 **({'input_revision':request['input_revision']} if request.get('input_revision') else {})})
            ids.append(key); deps.append(tid)
        # Bind only after shared work is complete, so cache identities include final dependencies.
        ready = all(store.job(parent)['status'] == 'completed' for parent in deps[1:])
        for parent in list(deps[1:]):
            for row in store.db.execute("SELECT j.id,j.status FROM dependencies d JOIN jobs j ON j.id=d.job_id WHERE d.dependency_id=? AND j.stage='judgment_observables'", (parent,)).fetchall():
                store.db.execute('INSERT OR IGNORE INTO run_jobs(run_id,job_id) VALUES(?,?)', (run, row['id']))
                deps.append(row['id'])
                ready = ready and row['status'] == 'completed'
        if ready:
            enqueue(store,run,'bindings',job['entity'],job['actor'],{'cell':request['cell'],'actor':job['actor'],'template_ids':ids, 'explicit_contexts': request.get('explicit_contexts', []), 'context_predicates': request.get('context_predicates', {})},deps)
    elif stage == 'template':
        store.merge_template(result)
        current = store.get_template(result['template_id'])
        for j in current['structure']['judgment_calls_needed']:
            if not j.get('observable_requirements'):
                shared_job = enqueue(store, run, 'judgment_observables',
                    result['template_id']+':'+digest([j['phrase'], j.get('note', '')])[:12], job['actor'],
                    {'template_id': result['template_id'], 'phrase': j['phrase'], 'note': j.get('note', ''),
                     'template_version': digest(result)}, [job['id']])
                for row in store.db.execute("SELECT child.id FROM dependencies d JOIN jobs child ON child.id=d.job_id WHERE d.dependency_id=? AND child.stage='bindings' AND child.status='pending'", (job['id'],)).fetchall():
                    store.db.execute('INSERT OR IGNORE INTO dependencies VALUES(?,?)', (row['id'], shared_job))
    elif stage == 'judgment_observables':
        template = store.get_template(result['template_id'])
        matches = [j for j in template['structure']['judgment_calls_needed']
                   if (j['phrase'], j.get('note', '')) == (result['phrase'], result.get('note', ''))]
        if len(matches) != 1:
            raise ValueError('Ambiguous judgment entry')
        entry = matches[0]
        if entry.get('observable_requirements') and entry['observable_requirements'] != result['observable_requirements']:
            raise ValueError('Conflicting observable requirements')
        entry['observable_requirements'] = result['observable_requirements']
        store.merge_template(template)
    elif stage == 'bindings':
        # An explicit corrected case version supersedes expansion from this same
        # immutable binding. New bindings or changed contracts still regenerate.
        versions = store.artifact(artifact_id)['provenance'].get('template_versions', {})
        for current in store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='cases' AND j.entity=? AND j.actor=?",(run,job['entity'],job['actor'])):
            correction=json.loads(current['payload'])
            parents={r[0] for r in store.db.execute('SELECT dependency_id FROM dependencies WHERE job_id=?',(current['id'],))}
            if (correction.get('supersedes_artifact') and job['id'] in parents
                    and correction.get('correction_contract_version') == digest(CONTRACTS['cases'])
                    and correction.get('template_versions',{}) == versions):
                return
        # Carry the exact library versions actually read, not a newer parallel update.
        request['template_versions'] = versions
        enqueue(store,run,'cases',job['entity'],job['actor'],request,[job['id']])
    elif stage == 'cases':
        # Simulation is explicitly selected later, never fan out over all cases.
        pass


CONTRACTS['cases'] += ' Follow inputs.judgment_completion_policy when supplied: for judgment-only one-dimensional sweeps, incomplete physical maneuvers are permitted only at the frozen minimum and maximum, at most one incomplete case at each endpoint. Every interior case must complete. Choose physically feasible ranges; no retrospective endpoint changes or hidden retries. Prefer one-dimensional sweeps so endpoint membership is unambiguous. Fewshots are draft implementation examples, never current evidence or legal thresholds.'
CONTRACTS['construction'] += ' When simulator_context.capture_requirements is supplied, implement it completely, using the reusable tick-neutral PipelineCapture helper at the supplied resource path. Capture every tick in the original recorded execution; do not run again for graphs. Save road.xodr, carla_recorder.log (additional_data=True), map identity, trace.jsonl, capture/native raw graphs, capture/evidence.jsonl and capture/manifest.json. Signal/stop/speed controls must physically exist with verified governed lanes. Record actual signal indications every frame. Do not replace a native map by an OpenDRIVE-only world that loses devices. Fewshots are references, not universal scene configurations or legal standards.'
CONTRACTS['cases'] += ' For numeric ego_speed probes, the general physical below/above margin is 5 mph converted to the threshold unit. The middle case retains its at name but commands 0.5 mph inside the compliant side, not exact equality. Deterministic normalization applies this policy. A low-speed or other justified override must provide speed_probe_policy.margin_mph and override_reason; never silently choose a different margin. Baselines are neutral definitions and are not simulated by default.'
CONTRACTS['construction'] += ' For speed probes, preserve the entire recording and declare the evaluation window in observed original times/frames; show that window explicitly in review videos. Use 0.5 mph tracking tolerance as an engineering criterion, not a legal tolerance. Capture ego lamp bits as well as other vehicle lamps. Validate visible indicator flashing in a suitably framed original RGB view; do not equate the API bit with emitted light or perception.'

CONTRACTS['construction'] += ' Active law observation atoms are provided as simulator_context.capture_requirements.required_atoms. Use PipelineCapture for original-frame capture; it automatically enables nine-point sight horizons when st.sight_distance is required, including through the executor environment. Spawned barrier/cone geometry is retained outside the local graph crop; geometric inclusion is not ego visibility. Do not replace any-body horizons with centre-only diagnostics.'

CONTRACTS['construction'] += ' For sight-distance capture, statically check incoming lane extent over the planned measured route against the declared search distance (the existing default is 230 m, with a 152.4 m statutory probe). Required sight-distance capture must cover every recorded frame. Extend an authored map before the original execution if its routes are too short; incomplete per-frame coverage is diagnostic evidence, not a usable replacement example. Map endpoints are not physical occluders; report any route limits explicitly and rebuild the construction. Do not alter a saved execution map during replay to fill missing measurements.'

CONTRACTS['construction'] += ' For repair_context requests, return repair:{diagnosis,evidence_references:[retained evidence paths],approved_case_sha256:<supplied hash>,changed_files:[actual changed construction file paths],scope:capture|controller_implementation|reporting|realize_approved_setup}. Diagnose the retained evidence, change the cause, and preserve the exact approved case and targets. A repeated unchanged construction is invalid. Repaired runners must include requested_variable_assignments in result.json, exactly matching world_setup and controller assignments in the supplied case. Continue within the existing run; do not create a duplicate campaign or new target sweep.'

CONTRACTS['construction'] += ' inputs.construction_group contains the full frozen comparison group. Prefer one configuration-driven runner supporting its members. To opt into deterministic reuse, return reuse_contract:{group_version:<exact supplied version>,config_file:<JSON file in files>,supported_case_ids:[explicit member IDs],capabilities:<supported physical mechanisms and branches>}. That JSON contains exact cell, actor and case objects plus any shared construction settings. All implementation files are frozen and reused unchanged; the runner reads this configuration. Support exceptions and subconditions explicitly. Omit the contract when independent construction is necessary; never restrict cases to fit a runner.'

CONTRACTS['cases'] += ' A law containing a judgment phrase may also have deterministic branch pairs where that phrase is not exercised or is an explicit fixed test assumption. Each such compliant_attempt/violating_attempt case MUST carry deterministic_branch:{source_clause:<exact nonempty substring of target law quote>,judgment_context:[{phrase,note,status:"not_exercised"|"fixed_assumption",reason,world_setup_refs:[canonical world_setup parameter names]}]}. Account for EVERY judgment entry with its exact phrase and note; fixed_assumption requires at least one referenced non-null world_setup assignment. Linked members use identical deterministic_branch context. Do not assert a subjective condition is physically measured, do not invent its cutoff, and never label a judgment_sweep. Retain sweep plans for all phrases, incomplete with precise missing_inputs when unsupported. In addition to judgment plans, prepare the deterministic target branches requested in simulator_context.case_selection_policy when supported: 113-2 reverse inside versus outside the intersection with no street-corner maneuver; 250-1 prior-entry yield under ordinary operative/uncontrolled context (inoperative-signal exception inactive); 250-4 complete halt versus no halt with other subjective conditions fixed explicitly. 250-2 approximate-simultaneity itself remains a judgment sweep unless an existing canonical world_setup parameter can explicitly fix that assumption. Do not replace any requested target branch by an unrelated speed-cap case.'
