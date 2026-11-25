"""Compare exact original-source officer and stopping-reference alternatives."""

import json
from pathlib import Path

from officer_reference_delivery_audit import audit_delivery, sha


PAIRS = {
    'officer_go_vs_hold': ('officer_controls_go', 'officer_controls_hold'),
    'officer_hold_vs_inactive': ('officer_controls_hold', 'officer_present_inactive'),
    'reference_hierarchy': ('stop_line_reference', 'crosswalk_reference',
                            'nearest_view_reference'),
}
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


def audit(comparison_id, attempts, package, *, diagnostic_fixture=False):
    suffixes = PAIRS.get(comparison_id)
    if suffixes is None or len(attempts) != len(suffixes):
        raise ValueError('Unknown or incomplete officer/reference comparison')
    attempts = [Path(path) for path in attempts]
    configs = [json.loads((path / 'config.json').read_text()) for path in attempts]
    for suffix, config in zip(suffixes, configs):
        if config.get('selected_case_id') != PREFIX + suffix:
            raise ValueError('Comparison has wrong exact case order')
    fixed = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
             'cameras', 'camera_mounts', 'actor_blueprints')
    for key in fixed:
        if any(config.get(key) != configs[0].get(key) for config in configs[1:]):
            raise ValueError('Fixed comparison condition changed: ' + key)
    for key in ('ego_start_xy_m', 'other_start_xy_m', 'other_release_frame'):
        if any(config['motion'].get(key) != configs[0]['motion'].get(key)
               for config in configs[1:]):
            raise ValueError('Fixed comparison condition changed: ' + key)
    captures = [json.loads((path / 'officer-reference-capture.json').read_text())
                for path in attempts]
    if comparison_id.startswith('officer_'):
        if captures[0].get('site_sha256') != captures[1].get('site_sha256'):
            raise ValueError('Fixed comparison condition changed: authored site')
        directions = [tuple(row['officer_program']['programmed_direction']
                            for row in capture['rows']) for capture in captures]
        if comparison_id == 'officer_go_vs_hold':
            if not (directions[0][:300] == directions[1][:300] and
                    directions[0][300:] == ('go',) * 300 and
                    directions[1][300:] == ('stop',) * 300):
                raise ValueError('Original programmed go/hold difference missing')
        elif directions[0] != ('stop',) * 600 or directions[1] != ('none',) * 600:
            raise ValueError('Original programmed hold/inactive difference missing')
    else:
        kinds = [json.loads((path / 'analysis-report.json').read_text())
                 ['reference_measurement']['reference_kind'] for path in attempts]
        if kinds != ['stop_line', 'near_crosswalk', 'nearest_view']:
            raise ValueError('Authored stopping-reference hierarchy differs')
        if len({capture['site_sha256'] for capture in captures}) != 3:
            raise ValueError('Authored reference alternatives do not use distinct sites')
    deliveries = [audit_delivery(path, package, PREFIX + suffix,
                                 diagnostic_fixture=diagnostic_fixture)
                  for path, suffix in zip(attempts, suffixes)]
    return {'format': 'c158196-officer-reference-comparison-audit',
            'comparison_id': comparison_id,
            'case_ids': [PREFIX + suffix for suffix in suffixes],
            'source_sha256': {suffix: sha(path / 'officer-reference-capture.json')
                              for path, suffix in zip(attempts, suffixes)},
            'delivery_audit_sha256': {
                suffix: delivery['analysis_sha256']
                for suffix, delivery in zip(suffixes, deliveries)},
            'fixed_conditions_checked': True,
            'programmed_or_authored_difference_observed': True,
            'officer_authority_observed': False if diagnostic_fixture else None,
            'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}
