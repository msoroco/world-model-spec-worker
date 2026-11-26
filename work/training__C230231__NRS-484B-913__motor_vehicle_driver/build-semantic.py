"""Write source-quoted hose semantic stages for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-913'
ACTOR = 'motor_vehicle_driver'
TEXT = 'A vehicle shall not be driven over any unprotected hose of a fire department when laid down on any highway or private way or place for use at any fire or alarm of fire or practice runs, without the consent of the fire department official in command.'
TEMPLATE = LAW + '@' + ACTOR
OBS = ('st.obstruction', 'rel.occupies', 'kin.path_length', 'st.highway',
       'ru.fire_apparatus', 'dev.human_direction', 'kin.velocity')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    assert assignment['law']['text'] == TEXT
    desc = json.loads((HERE / 'draft-exact/witness_1/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': 'C230231', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen road/travel/fire-hose cell; original way, hose, protection, passage and consent require independent sources.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'unprotected hose of a fire department', 'note': 'Department affiliation, asset identity and all protection arrangements need independent inventory and pixels.'},
        {'phrase': 'highway or private way or place for use at any fire or alarm of fire or practice runs', 'note': 'Way dedication/public access, actual route placement and department use purpose need separate sources.'},
        {'phrase': 'driven over', 'note': 'Original vehicle footprint and motion measure passage; no invented legal overlap or speed cutoff.'},
        {'phrase': 'consent of the fire department official in command', 'note': 'Official identity/status and communication content, timing and scope need source review; no gesture inference.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Covered vehicle and human driver approach a qualifying department hose on a qualifying way for specified use.',
            'source_clause': 'a vehicle ... hose of a fire department ... highway or private way or place ... fire or alarm of fire or practice runs'},
            'obligation': {'description': 'Observe original driven-over passage, protection arrangements and communication; reserve legal conclusion.',
                'type': 'must_not', 'source_clause': 'shall not be driven over any unprotected hose', 'numeric_conditions': []},
            'exceptions': [{'description': 'Documented consent by the fire department official in command, with identity, content, timing and scope.',
                            'source_clause': 'without the consent of the fire department official in command'}],
            'timing': {'description': 'Point passage event in original 600-frame capture; consent timing is separately sourced.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'driven_hose_overlap', 'kind': 'subject_behavior', 'range_or_domain': 'original full-body footprint and motion'},
            {'name': 'hose_protection_and_status', 'kind': 'world_setup', 'range_or_domain': 'independent asset and protection review'},
            {'name': 'command_communication', 'kind': 'world_setup', 'range_or_domain': 'independent command log or explicit no communication'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    groups = [('st.obstruction', 'ru.fire_apparatus'), ('st.highway',),
              ('rel.occupies', 'kin.path_length', 'kin.velocity'), ('dev.human_direction',)]
    observed = []
    for i, judgment in enumerate(judgments, 1):
        names = groups[i - 1]
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name} for name in names],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original frame and independent source review for ' + name} for name in names],
            'limitations': ['Synthetic source-shaped pixels do not establish authority, consent, physical passage or legal outcome.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % i),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C230231', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'hose_way_context', 'value': 'road/travel/fire_hose', 'rationale': 'Frozen catalog cell, subject to original review.'}],
        'variable_parameters': [{'name': 'driven_hose_overlap', 'kind': 'subject_behavior', 'range_or_domain': 'observed route clear or driven overlap', 'used_by_laws': [LAW]},
            {'name': 'target_cross_hose', 'kind': 'controller', 'range_or_domain': 'route around or across', 'used_by_laws': [LAW]},
            {'name': 'command_communication', 'kind': 'world_setup', 'range_or_domain': 'explicit none or sourced consent', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Observe way and hose context without a passage target.',
        'variable_assignments': {'driven_hose_overlap': {'kind': 'subject_behavior', 'value': None},
            'target_cross_hose': {'kind': 'controller', 'value': None},
            'command_communication': {'kind': 'world_setup', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': desc}]
    for suffix in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'):
        cross = suffix != 'witness_1'
        consent = suffix == 'exception_1_2'
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'hose_passage' if suffix.startswith('witness') else 'command_consent',
            'rationale': 'Request ' + ('crossing' if cross else 'route around') + ' with ' + ('sourced consent' if consent else 'explicit no communication') + '; measure originals without legal label.',
            'deliberate_differences': ['target_cross_hose'] if suffix.startswith('witness') else ['command_communication'],
            'variable_assignments': {'driven_hose_overlap': {'kind': 'subject_behavior', 'value': None},
                'target_cross_hose': {'kind': 'controller', 'value': cross},
                'command_communication': {'kind': 'world_setup', 'value': 'documented_consent' if consent else 'explicit_none'}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'driven_hose_overlap',
                'comparison_or_standard': 'source-reviewed hose extent and command communication',
                'target_value_or_branch': suffix}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C230231', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{'sweep_id': 'hose-passage-command-review',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Synthetic diagnostics preserve source joins while original hose status, protection and command authority remain open.',
            'missing_inputs': ['Independent original way, hose and command sources.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
