"""Independent source-bound comparison of the two graded-standing attempts."""
import json
from pathlib import Path

from measure import SOURCES, measure

DUTIES = ('engine_operation', 'parking_brake_state', 'front_wheel_orientation')


def duty_observations(measured):
    """Keep the three statutory observations separate, without legal thresholds."""
    return {
        'engine_operation': measured['engine_running_any'],
        'parking_brake_state': measured['parking_brake_unset_any'],
        'front_wheel_orientation':
            measured['front_wheel_heading_to_curb_deg_range'],
    }


def isolated_duty_contrast(reference, contrast, reference_hashes,
                           contrast_hashes, duty, diagnostic=False):
    """A CPU control check: exactly one observed duty may vary."""
    if duty not in DUTIES:
        raise ValueError('Unknown statutory duty')
    left = measure(reference, reference_hashes, diagnostic=diagnostic)
    right = measure(contrast, contrast_hashes, diagnostic=diagnostic)
    fixed = {
        'grade': left['grade_slope_fraction'] == right['grade_slope_fraction'],
        'curb': left['right_curb_y_m'] == right['right_curb_y_m'],
        'unattended_window': left['unattended_frames'] == right['unattended_frames'],
        'duration_and_rate': (left['frames'], left['rate_hz']) ==
                             (right['frames'], right['rate_hz']),
    }
    observed = (duty_observations(left), duty_observations(right))
    for other in DUTIES:
        fixed['other_' + other] = observed[0][other] == observed[1][other] if other != duty else True
    if not all(fixed.values()) or observed[0][duty] == observed[1][duty]:
        raise ValueError('Single-duty fixed-condition contrast absent')
    return {'format': 'c276263-isolated-duty-contrast-v1', 'duty': duty,
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_native',
            'fixed_checks': fixed, 'reference_observation': observed[0][duty],
            'contrast_observation': observed[1][duty],
            'source_hashes': [reference_hashes, contrast_hashes],
            'physical_or_legal_acceptance': False}


def compare(reference, contrast, reference_hashes, contrast_hashes,
            diagnostic=False):
    left = measure(reference, reference_hashes, diagnostic=diagnostic)
    right = measure(contrast, contrast_hashes, diagnostic=diagnostic)
    fixed = {
        '600_frames_20hz': all(m['frames'] == 600 and m['rate_hz'] == 20
                               for m in (left, right)),
        'same_grade': left['grade_slope_fraction'] == right['grade_slope_fraction'],
        'same_curb': left['right_curb_y_m'] == right['right_curb_y_m'],
        'same_unattended_window': left['unattended_frames'] == right['unattended_frames'],
        'same_engine_operation': left['engine_running_any'] == right['engine_running_any'],
    }
    differences = {
        'parking_brake_state': left['parking_brake_unset_any'] != right['parking_brake_unset_any'],
        'front_wheel_orientation':
            left['front_wheel_heading_to_curb_deg_range'] !=
            right['front_wheel_heading_to_curb_deg_range'],
    }
    if not all(fixed.values()):
        raise ValueError('Fixed original comparison condition differs')
    if not all(differences.values()):
        raise ValueError('Declared original brake/wheel contrast absent')
    return {'format': 'c276263-independent-comparison-v1',
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_native',
            'fixed_checks': fixed, 'difference_checks': differences,
            'reference_source_hashes': reference_hashes,
            'contrast_source_hashes': contrast_hashes,
            'statutory_duty_observations': {
                'reference': duty_observations(left),
                'contrast': duty_observations(right)},
            'isolates_individual_duties': False,
            'reason': 'The selected pair changes brake and wheel together; each duty is assessed separately from original sources, and isolated causal claims need fixed-condition pairs',
            'physical_or_legal_acceptance': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--reference-hashes', required=True)
    parser.add_argument('--contrast-hashes', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Use fresh comparison output')
    hashes = [json.loads(Path(path).read_text()) for path in
              (args.reference_hashes, args.contrast_hashes)]
    if any(set(row) != set(SOURCES) for row in hashes):
        raise ValueError('Complete original source hash inventory required')
    result = compare(args.reference, args.contrast, *hashes)
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
