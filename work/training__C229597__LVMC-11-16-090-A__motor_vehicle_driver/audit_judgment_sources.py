"""Fail-closed CPU review of the two LVMC 11.16.090(A) judgment sources.

The returned unknowns are review tasks, never positive statutory findings.
"""
import argparse
import json
from pathlib import Path

from audit_saved_review_sources import audit as audit_integrity

LAW = 'LVMC-11-16-090-A'
PHRASES = ('exhibition of power or speed', 'on a highway')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(attempt):
    attempt = Path(attempt)
    integrity = audit_integrity(attempt)
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    report = json.loads((attempt / 'analysis-report.json').read_text())
    result = json.loads((attempt / 'result.json').read_text())
    exhibition = json.loads((attempt / 'channels/exhibition_episode_context.json').read_text())['exhibition_episode_context']
    highway = json.loads((attempt / 'channels/original_highway_survey.json').read_text())['original_highway_survey']
    require(result['case_id'] == integrity['case_id'], 'Judgment case identity differs')
    require(provenance.get('provenance_kind') == 'synthetic_fixture',
            'CPU fixture proof requires explicit synthetic provenance')
    require(exhibition.get('source_kind') == 'synthetic_fixture'
            and highway.get('source_kind') == 'synthetic_fixture',
            'Judgment context provenance differs')
    require(exhibition.get('exhibition_review') == 'unresolved'
            and highway.get('highway_classification') == 'unresolved',
            'Synthetic judgment source cannot assert a statutory outcome')
    require(highway.get('jurisdiction_source') is None
            and highway.get('map_name') is None,
            'Synthetic road source cannot assert reviewed highway context')
    require(exhibition.get('participant_source') ==
            'original camera views and ego trace; other participants unclassified',
            'Participant and episode review context differs')
    measured = result['measured_values']
    require(measured['frames'] == 600 and measured['first_time_s'] == 0.0
            and measured['last_time_s'] == 29.95,
            'Complete 30-second motion episode required')
    for item in report['measurements'].values():
        require(item['value'] == measured,
                'Judgment physical measurements differ from saved source report')
    require(not result.get('accepted') and not result.get('legal_verdict_claimed')
            and not report.get('legal_verdict_claimed'),
            'Judgment source claims acceptance or legal verdict')
    return {
        'format': 'c229597-judgment-source-audit-v1',
        'case_id': result['case_id'], 'law_id': LAW,
        'source_integrity': integrity,
        'physical_motion': {'frames': measured['frames'],
                            'maximum_speed_mps': measured['maximum_speed_mps'],
                            'maximum_acceleration_mps2': measured['maximum_acceleration_mps2'],
                            'speed_increase_mps': measured['speed_increase_mps'],
                            'source': 'original saved trace and frame map'},
        'judgments': [
            {'phrase': PHRASES[0], 'status': 'unknown',
             'reason': 'Synthetic motion and throttle request do not establish exhibition or intent',
             'required_original_sources': ['four camera streams', 'complete episode',
                                           'participant and surrounding-event review']},
            {'phrase': PHRASES[1], 'status': 'unknown',
             'reason': 'Diagnostic OpenDRIVE lane does not establish highway or jurisdiction',
             'required_original_sources': ['original road map', 'route-position join',
                                           'independent jurisdiction/highway review']},
        ],
        'engineering_axis_only': 'requested peak-phase throttle',
        'physical_response_range_verified': False,
        'statutory_threshold_claimed': False,
        'native_executed': False, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), sort_keys=True))
