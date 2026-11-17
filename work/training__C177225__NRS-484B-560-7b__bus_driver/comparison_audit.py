"""Independent saved comparison audit; no statutory or physical verdict."""
import json
from pathlib import Path

from finalize_direction import process_saved, signal_case_id


FIXED_CONFIG = ('law_id', 'cell_id', 'actor', 'direction', 'rate_hz',
                'duration_s', 'frames', 'cameras', 'rail_asset_blueprint',
                'required_atoms', 'source_packets', 'weather',
                'authored_test_context')


def audit_pair(reference, contrast, reference_config, contrast_config,
               reference_signal, contrast_signal):
    if reference_config.get('case_id') != signal_case_id('reference') or (
            contrast_config.get('case_id') != signal_case_id('contrast')):
        raise ValueError('Exact reference/contrast case identities required')
    changed = [key for key in FIXED_CONFIG
               if reference_config.get(key) != contrast_config.get(key)]
    if changed:
        raise ValueError('Fixed comparison configuration changed: ' + ', '.join(changed))
    for name, signal in (('reference', reference_signal), ('contrast', contrast_signal)):
        if (signal.get('authorized') is not True or
                signal.get('hand_signal') != 'STOP' or
                signal.get('crossing_id') != 'c177225_authored_rail_crossing' or
                signal.get('direction') != reference_config['direction'] or
                not signal.get('bus_id') or not signal.get('officer_id')):
            raise ValueError('Missing recipient-bound officer direction in ' + name)
    for key in ('direction', 'hand_signal', 'crossing_id', 'authorized'):
        if reference_signal.get(key) != contrast_signal.get(key):
            raise ValueError('Fixed officer direction changed: ' + key)
    for name, observation in (('reference', reference), ('contrast', contrast)):
        if (observation.get('native_frames') != reference_config['frames'] or
                set(observation.get('saved_camera_sources', {})) !=
                {'overview', 'approach', 'reference_corner', 'driver_reference'} or
                len(observation.get('saved_source_sha256', {})) < 5 or
                not observation.get('officer_direction_witnessed_frames')):
            raise ValueError('Missing complete saved source binding in ' + name)
    if reference.get('source_kind') != contrast.get('source_kind'):
        raise ValueError('Comparison mixes source provenance')
    observed_difference = (
        reference.get('observed_complete_stop_before_line') is True and
        contrast.get('observed_complete_stop_before_line') is False and
        contrast.get('observed_crossing_entry') is True)
    return {
        'format': 'c177225-independent-comparison-audit',
        'case_ids': [signal_case_id('reference'), signal_case_id('contrast')],
        'fixed_config_fields_checked': list(FIXED_CONFIG),
        'deliberate_difference': 'bus_obeys_officer_direction',
        'observed_response_difference': observed_difference,
        'status': 'software_measurement_pair_observed' if observed_difference else 'response_not_established',
        'source_kind': reference['source_kind'],
        'physical_acceptance_claimed': False,
        'legal_verdict': None,
    }


def audit_saved(reference_root, contrast_root, *, source_kind='original_native'):
    roots = [Path(reference_root), Path(contrast_root)]
    observations = [process_saved(root, source_kind=source_kind) for root in roots]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    signals = [json.loads((root / 'officer_signal_definition.json').read_text())
               for root in roots]
    return audit_pair(*observations, *configs, *signals)
