"""Bind two ordinary red-curb contrasts to current selected synthetic sources."""
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
EXPECTED_MAIN = (True, False)
EXPECTED_SIGN = (False, True)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def source(slug, saved, selected, manifest_sha):
    row = saved[slug]
    case_id = WORK.name + '__' + slug
    analysis = Path(row['scratch_result']) / 'v0001/analysis'
    require(REPO / '.runtime-work' in analysis.resolve().parents,
            'Selected source outside scratch')
    selection = read(analysis / 'candidate-selection.json')
    require(selection['case_id'] == case_id and selection['candidate_id'] == 'primary' and
            selection['manifest_sha256'] == manifest_sha and
            selection['construction_sha256'] == selected[case_id]['construction_sha256'],
            'Current selected source differs: ' + slug)
    processing = Path(row['scratch_result']) / 'v0001/processing.json'
    require(sha(processing) == row['processing']['processing']['sha256'] and
            read(processing)['recorded_only'] is True,
            'Saved processing differs: ' + slug)
    construction = read(WORK / selected[case_id]['construction'])
    runner = next(item['content'] for item in construction['files']
                  if item['path'] == 'runner.py')
    require("library.find('vehicle.tesla.model3')" in runner,
            'Ordinary actor Native blueprint not selected: ' + slug)
    return {'slug': slug, 'case_id': case_id, 'analysis': analysis,
            'config': read(analysis / 'config.json'),
            'map': read(analysis / 'native-map-readback.json'),
            'result': read(analysis / 'result.json'),
            'trace': [json.loads(line) for line in (analysis / 'trace.jsonl').read_text().splitlines()],
            'processing_sha256': sha(processing)}


def audit():
    manifest_path = WORK / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    selected = {item['case_id']: item for item in read(manifest_path)['cases']}
    saved = {item['case']: item for item in read(WORK / 'current-short-selected-saved-index.json')['rows']}
    planned = {item['comparison_id'].rsplit('__', 1)[-1]: item
               for item in read(WORK / 'case-plan.json')['comparisons']}
    reference, contrast, signed = (source(slug, saved, selected, manifest_sha)
                                   for slug in ('reference','contrast','ordinary_red_signed'))
    require(planned['comparison_main']['case_ids'] == [reference['case_id'], contrast['case_id']] and
            planned['ordinary_sign_pair']['case_ids'] == [reference['case_id'], signed['case_id']],
            'Planned ordinary comparison membership differs')
    for key in ('paint_color','red_curb_start_x_m','red_curb_end_x_m','curb_y_m'):
        require(reference['map'][key] == contrast['map'][key] == signed['map'][key],
                'Red curb source differs: ' + key)
    require(sha(reference['analysis'] / 'native-map-readback.json') ==
            sha(contrast['analysis'] / 'native-map-readback.json'),
            'Main comparison changed the Native map')
    for left, right, difference in ((reference, contrast, 'requested_target_x_m'),
                                    (reference, signed, 'sign_classes')):
        for key in ('actor','cell_id','law_id','cameras','capture_frames'):
            require(left['config'].get(key) == right['config'].get(key),
                    'Ordinary comparison fixed config differs: ' + key)
        require(left['config']['requested_target_x_m'] == right['config']['requested_target_x_m']
                if difference == 'sign_classes' else
                left['config']['requested_target_x_m'] != right['config']['requested_target_x_m'],
                'Ordinary comparison target differs incorrectly')
    main = (reference['result']['measured_values']['red_curb_stop_or_park_observed'],
            contrast['result']['measured_values']['red_curb_stop_or_park_observed'])
    require(main == EXPECTED_MAIN, 'Main red-curb source contrast missing')
    require(reference['map'].get('sign_readback') is None and
            signed['map']['sign_readback']['present'] is True,
            'Ordinary sign source contrast missing')
    signs = (False, signed['map']['sign_readback']['present'])
    require(signs == EXPECTED_SIGN, 'Ordinary sign expectation differs')
    require(reference['result']['measured_values']['red_curb_stop_or_park_observed'] is True and
            signed['result']['measured_values']['red_curb_stop_or_park_observed'] is True,
            'Sign comparison changed red-curb occupancy')
    fields = ('frame','time_s','position','heading_deg','speed_mps')
    require(len(reference['trace']) == len(signed['trace']) == 240 and
            all(all(a.get(k) == b.get(k) for k in fields)
                for a,b in zip(reference['trace'], signed['trace'])),
            'Sign comparison changed synthetic ego motion')
    return {'format': 'c150142-current-ordinary-comparisons-v1',
            'passed': True, 'manifest_sha256': manifest_sha,
            'comparisons': [
                {'comparison_id': planned['comparison_main']['comparison_id'],
                 'case_ids': [reference['case_id'], contrast['case_id']],
                 'planned_difference': 'red_curb_stop_or_park',
                 'observed_red_curb_stop_or_park': list(main),
                 'fixed_map_sha256': sha(reference['analysis'] / 'native-map-readback.json')},
                {'comparison_id': planned['ordinary_sign_pair']['comparison_id'],
                 'case_ids': [reference['case_id'], signed['case_id']],
                 'planned_difference': 'sign_present',
                 'observed_sign_present': list(signs),
                 'matching_synthetic_trace_frames': 240}],
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
