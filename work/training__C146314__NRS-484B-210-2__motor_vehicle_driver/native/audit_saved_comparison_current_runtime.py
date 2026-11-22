"""Independent comparison of current retained-source saved attempts.

The CPU fixture sources are diagnostic. A passing audit establishes comparison
code and source binding, never original physical or legal acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

import check
import measure_raw


ROOT = Path(__file__).resolve().parents[3]
AID = Path(__file__).resolve().parents[1].name


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def load(witness, candidate):
    prefix = ROOT / '.runtime-work/c146314-current-matrix' / witness / candidate
    attempt = prefix / 'compat'
    receipt = read(prefix / 'saved/v0001/processing.json')
    report = read(Path(receipt['result']).parent / 'analysis-report.json')
    config = read(attempt / 'config.json')
    track = check.rows(attempt / 'requested-tracks.jsonl')
    rows = measure_raw.read_jsonl(attempt / 'native-raw-actors.jsonl')
    frames = measure_raw.read_jsonl(attempt / 'video_frames.jsonl')
    return {'attempt': attempt, 'receipt': receipt, 'report': report,
            'config': config, 'track': track, 'rows': rows, 'frames': frames}


def audit_pair(reference, contrast, candidate):
    selected_fields = ('selected_case_id', 'supported_case_ids', 'case')
    check.validate_pair({k: v for k, v in reference['config'].items()
                         if k not in selected_fields}, reference['track'],
                        {k: v for k, v in contrast['config'].items()
                         if k not in selected_fields}, contrast['track'])
    for witness, item in (('reference', reference), ('contrast', contrast)):
        cfg = item['config']
        require(cfg['selected_case_id'] == AID + '__' + witness and
                cfg['supported_case_ids'] == [cfg['selected_case_id']] and
                cfg['case']['case_id'] == cfg['selected_case_id'] and
                cfg['case']['paired_probe_id'] == AID + '__clearance_sweep' and
                cfg['case']['deliberate_differences'] == ['commanded_lateral_apex'] and
                cfg['case']['sweep_point']['commanded_lateral_apex'] ==
                cfg['requested_lateral_apex_y_m'],
                'Selected sweep identity or changed variable differs')
    measured = []
    for witness, item in (('reference', reference), ('contrast', contrast)):
        attempt, receipt, report = item['attempt'], item['receipt'], item['report']
        case = AID + '__' + witness
        require(receipt.get('case_id') == report.get('case_id') == case and
                receipt.get('candidate_id') == report.get('candidate_id') == candidate and
                receipt.get('passed') is True and receipt.get('recorded_only') is True and
                receipt.get('originals_preserved') is True,
                'Saved comparison identity or processing differs')
        hashes = receipt.get('original_source_hashes', {})
        for source in ('native-raw-actors.jsonl', 'video_frames.jsonl',
                       'requested-tracks.jsonl', 'config.json'):
            require(hashes.get(source) == sha(attempt / source),
                    'Saved comparison source changed: ' + source)
        require(report.get('source_kind') == 'synthetic_native_sample' and
                report.get('physical_acceptance_claimed') is False and
                report.get('legal_verdict_claimed') is False,
                'Diagnostic comparison claimed original or legal acceptance')
        independent = measure_raw.measure(item['rows'], item['frames'])
        require(independent['source_kind'] == report['source_kind'] and
                independent['frames'] == 240 and
                independent['observed_right_pass_frames'] > 0,
                'Saved comparison lacks synchronized right-pass observations')
        gap = report['measurements']['measured_pass_body_clearance_m']
        time = report['measurements']['minimum_positive_time_to_lead_center_s']
        for measurement in (gap, time):
            require(measurement['sources'] == {
                'native-raw-actors.jsonl': hashes['native-raw-actors.jsonl'],
                'video_frames.jsonl': hashes['video_frames.jsonl']},
                    'Saved comparison measurement source changed')
        positive_times = [row['time_to_lead_center_s'] for row in independent['observations']
                          if row['time_to_lead_center_s'] is not None and
                          row['time_to_lead_center_s'] > 0]
        require(abs(gap['value'] - independent['minimum_pass_body_surface_gap_m']) < 1e-9 and
                positive_times and abs(time['value'] - min(positive_times)) < 1e-9,
                'Saved comparison measurement differs from retained sources')
        measured.append(gap['value'])
    require(measured[0] > measured[1],
            'Saved reference gap does not exceed contrast gap')
    return {'candidate_id': candidate, 'reference_gap_m': measured[0],
            'contrast_gap_m': measured[1], 'source_kind': 'synthetic_native_sample',
            'diagnostic_only': True, 'legal_safety_verdict': None}


def prove():
    positives = []; negatives = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        reference, contrast = load('reference', candidate), load('contrast', candidate)
        positives.append(audit_pair(reference, contrast, candidate))

        def reject(label, left, right, expected):
            try:
                audit_pair(left, right, candidate)
            except ValueError as error:
                require(expected in str(error), label + ': wrong rejection: ' + str(error))
                negatives.append(label + '-' + candidate)
            else:
                raise AssertionError('Saved comparison mutation accepted: ' + label)

        altered = copy.deepcopy(reference)
        altered['receipt']['original_source_hashes']['native-raw-actors.jsonl'] = '0' * 64
        reject('changed-source', altered, contrast, 'source changed')
        altered = copy.deepcopy(contrast)
        altered['config']['lead_requested_speed_mps'] += 1
        reject('changed-fixed-condition', reference, altered, 'fixed config condition')
        altered = copy.deepcopy(contrast)
        altered['report']['measurements']['measured_pass_body_clearance_m']['value'] += 1
        reject('altered-measurement', reference, altered, 'measurement differs')
        altered = copy.deepcopy(contrast)
        altered['report']['source_kind'] = 'original_native'
        reject('false-original-provenance', reference, altered, 'claimed original')
    return {'format': 'c146314-current-saved-comparison-proof-v1',
            'passed': True, 'positive_diagnostic_pairs': positives,
            'negative_rejections': negatives,
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_safety_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
