"""Independent source-bound CPU comparison for the unselected 300 ft drafts."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SIDES = ROOT / 'signal-300-sides-draft-index.json'
AT = ROOT / 'signal-300-at-draft-index.json'
SUFFIXES = ('below_86', 'at', 'above_97')
TARGETS = (86.0, 91.44, 97.0)
REPORTS = (
    '.runtime-work/c109749-signal-300-86-primary-compat-v1/analysis-report.json',
    '.runtime-work/c109749-signal-300-at-primary-compat-v3/analysis-report.json',
    '.runtime-work/c109749-signal-300-97-primary-compat-v1/analysis-report.json',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_sources():
    sides = json.loads(SIDES.read_text())['cases']
    at = json.loads(AT.read_text())
    entries = (sides[0], at, sides[1])
    sources = []
    for suffix, target, entry, report_path in zip(SUFFIXES, TARGETS, entries, REPORTS):
        folder = ROOT / 'cases' / ('signal_advance_300_' + suffix)
        path, recipe_path = folder / 'diagnostic.json', folder / 'diagnostic-recipe.json'
        require(entry['case_id'].endswith('__signal_advance_300_' + suffix), 'draft index case mismatch')
        expected = entry.get('signal_target_m', entry.get('target_m'))
        require(expected == target, 'draft target mismatch')
        if 'diagnostic_sha256' in entry:
            require(sha(path) == entry['diagnostic_sha256'], 'diagnostic source hash mismatch')
            require(sha(recipe_path) == entry['recipe_sha256'], 'recipe hash mismatch')
        recipe = json.loads(recipe_path.read_text())
        require(recipe['generator']['sha256'] == sha(path), 'generator source hash mismatch')
        require(recipe['sources'][0]['sha256'] == sha(path), 'recipe source hash mismatch')
        data = json.loads(path.read_text())
        history = [json.loads(line) for line in data['files']['interaction_history.jsonl'].splitlines()]
        report_file = REPO / report_path
        require(report_file.is_file(), 'saved compatibility report missing')
        report = json.loads(report_file.read_text())
        require(report['case_id'] == entry['case_id'], 'saved report case mismatch')
        sources.append({'suffix': suffix, 'target': target, 'case_id': entry['case_id'],
                        'diagnostic_sha256': sha(path), 'recipe_sha256': sha(recipe_path),
                        'report_sha256': sha(report_file), 'data': data, 'history': history,
                        'report': report})
    return sources


def audit(sources):
    require(len(sources) == 3, 'three exact grid sources required')
    base = sources[1]
    base_history = base['history']
    fixed_geometry = base['data']['files']['intersection_geometry.json']
    fixed_videos = base['data']['videos']
    outcomes = []
    for source in sources:
        rows = source['history']
        require(len(rows) == 210, 'history length changed')
        require(source['data']['files'].get('intersection_geometry.json') == fixed_geometry,
                'intersection geometry changed')
        require(source['data']['videos'] == fixed_videos, 'camera source plan changed')
        for i, (row, baseline) in enumerate(zip(rows, base_history)):
            require(row['frame'] == baseline['frame'] and row['time_s'] == baseline['time_s'],
                    'frame timeline changed')
            require(row['oncoming'] == baseline['oncoming'] and
                    row['reciprocal'] == baseline['reciprocal'], 'other actor changed')
            require(row['ego_heading_deg'] == baseline['ego_heading_deg'],
                    'turn heading changed')
            require(row['ego_left_indicator'] == baseline['ego_left_indicator'],
                    'signal history changed')
            if i >= 145:
                require(row['ego'] == baseline['ego'], 'yield or turn tail changed')
        require(all(not row['ego_left_indicator'] for row in rows[:10]),
                'full signal onset missing')
        require(all(row['ego_left_indicator'] for row in rows[10:209]),
                'signal interrupted before turn')
        require(rows[10]['ego_heading_deg'] == 0 and rows[200]['ego_heading_deg'] == 0
                and abs(rows[201]['ego_heading_deg']) > 15, 'turn onset changed')
        # The generator's only approach change is a linear x trajectory through
        # the common frame-144 yield point. Check every sample independently.
        x0 = rows[10]['ego']['position_xy_m'][0]
        x144 = rows[144]['ego']['position_xy_m'][0]
        step = (x144 - x0) / 134
        speed = step * 20
        for i in range(145):
            ego = rows[i]['ego']
            require(abs(ego['position_xy_m'][0] - (x0 + (i - 10) * step)) < 2e-5,
                    'pre-yield trajectory changed')
            require(abs(ego['velocity_xy_mps'][0] - speed) < 2e-5,
                    'pre-yield speed changed unexpectedly')
            require(ego['position_xy_m'][1] == 1.75, 'ego lane changed')
        require(abs(x144 - 95.54) < 1e-5, 'common yield point changed')
        # The front-reference offset is fixed by the source construction.
        # Compare distances by differences in source x at indicator onset;
        # the report supplies the absolute measurement for each exact case.
        observed = source['report']['measurements']['signal_advance_observation']['value']
        distance = observed['observed_continuous_approach_distance_m']
        require(abs(distance - source['target']) < .001, 'saved distance differs from target')
        require(observed['continuous_start_frame'] == rows[10]['frame'],
                'saved signal onset differs from source')
        require(observed['probes']['91.44']['full_signal_onset_observed'] is True,
                'saved report lacks onset')
        require(observed['probes']['91.44']['observable_distance_met'] is
                (source['target'] >= 91.44), 'saved threshold classification differs')
        require(observed['district_classification'] == 'unresolved' and
                observed['legal_verdict_asserted'] is False and
                source['report']['legal_verdict_asserted'] is False,
                'unsupported legal verdict')
        outcomes.append({'case_id': source['case_id'], 'target_m': source['target'],
                         'observed_saved_m': distance, 'onset_ego_x_m': x0,
                         'pre_yield_ego_speed_mps': speed,
                         'threshold_met': observed['probes']['91.44']['observable_distance_met'],
                         'source_sha256': source['diagnostic_sha256'],
                         'recipe_sha256': source['recipe_sha256'],
                         'saved_report_sha256': source['report_sha256']})
    for left, right in zip(outcomes, outcomes[1:]):
        require(abs((left['onset_ego_x_m'] - right['onset_ego_x_m']) -
                    (right['target_m'] - left['target_m'])) < .001,
                'source distance delta differs from declared target delta')
        require(left['pre_yield_ego_speed_mps'] < right['pre_yield_ego_speed_mps'],
                'declared pre-yield speed ordering changed')
    return outcomes


def negative_proofs(sources):
    mutations = {
        'missing_source': lambda s: s[0]['data']['files'].pop('intersection_geometry.json'),
        'changed_oncoming': lambda s: s[0]['history'][40]['oncoming']['position_xy_m'].__setitem__(0, 1000),
        'interrupted_signal': lambda s: s[1]['history'][50].__setitem__('ego_left_indicator', False),
        'changed_saved_distance': lambda s: s[2]['report']['measurements']['signal_advance_observation']['value'].__setitem__('observed_continuous_approach_distance_m', 85),
        'nonlinear_approach': lambda s: s[2]['history'][50]['ego']['position_xy_m'].__setitem__(0, 1000),
        'changed_yield_tail': lambda s: s[0]['history'][145]['ego']['position_xy_m'].__setitem__(0, 1000),
    }
    rejected = {}
    for name, mutate in mutations.items():
        altered = copy.deepcopy(sources)
        mutate(altered)
        try:
            audit(altered)
        except (ValueError, KeyError) as exc:
            rejected[name] = str(exc)
        else:
            raise ValueError('negative comparison mutation accepted: ' + name)
    return rejected


if __name__ == '__main__':
    sources = read_sources()
    print(json.dumps({'format': 'worker-signal-300-grid-independent-comparison-v1',
                      'cases': audit(sources), 'rejected_mutations': negative_proofs(sources),
                      'declared_difference': 'target distance and pre-yield ego x/speed',
                      'fixed_conditions': ['frame timeline', 'junction geometry', 'camera source plan',
                                           'oncoming and reciprocal histories', 'signal onset and continuity',
                                           'ego yield and turn tail'],
                      'source_kind': 'synthetic diagnostic only',
                      'native_physical_or_legal_acceptance_claimed': False}, indent=2))
