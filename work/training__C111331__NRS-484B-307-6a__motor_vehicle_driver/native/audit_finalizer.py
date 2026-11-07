"""Independent source/contract/result audit of eight saved C111331 bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    summary_path = HERE / 'saved-finalizer-summary.json'
    summary = json.loads(summary_path.read_text())
    manifest = HERE / 'package-manifest.json'
    if summary['manifest_sha256'] != sha(manifest) or summary['accepted_recording_claimed'] or len(summary['rows']) != 8:
        raise ValueError('Exact saved proof manifest or scope differs')
    indexed = {(r['case'], r['candidate']): r for r in summary['rows']}
    if len(indexed) != 8:
        raise ValueError('Eight independent saved rows required')
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            item = indexed[case, candidate]
            source = HERE / 'synthetic-saved' / case / candidate
            video = REPO / '.runtime-work/c111331-signal-cpu-video' / case / candidate / 'signal_reference.mkv'
            retained = HERE / 'saved-receipts' / case / candidate
            report = json.loads((retained / 'analysis-report.json').read_text())
            result = json.loads((retained / 'result.json').read_text())
            contract = HERE / 'measurement-contracts' / (case + '.json')
            construction = HERE / 'package-candidates' / case / candidate / 'construction.json'
            if item['manifest_sha256'] != sha(manifest) or item['construction_sha256'] != sha(construction) or item['measurement_contract_sha256'] != sha(contract):
                raise ValueError('Saved result construction/contract hash differs')
            if item['analysis_report_sha256'] != sha(retained / 'analysis-report.json') or item['result_sha256'] != sha(retained / 'result.json') or item['positive_log_sha256'] != sha(retained / 'positive-analysis.log') or item['negative_log_sha256'] != sha(retained / 'negative-analysis.log') or item['wrong_video_log_sha256'] != sha(retained / 'wrong-video-analysis.log') or item['wrong_join_log_sha256'] != sha(retained / 'wrong-join-analysis.log'):
                raise ValueError('Saved result/log hash differs')
            if item['negative_error'] not in (retained / 'negative-analysis.log').read_text() or item['wrong_video_error'] not in (retained / 'wrong-video-analysis.log').read_text() or item['wrong_join_error'] not in (retained / 'wrong-join-analysis.log').read_text() or item['pinned_native_attempt_validation'] != 'passed' or item['physical_success_claimed']:
                raise ValueError('Missing-source negative or physical scope differs')
            if report['selected'] or report['physical_acceptance_claimed'] or report['legal_verdict_claimed'] or result['accepted'] or result['setup_confirmed'] or result['behavior_attempted'] or result['maneuver_completed']:
                raise ValueError('Synthetic result promoted to physical or legal evidence')
            source_hashes = {'native_samples.jsonl': sha(source / 'native_samples.jsonl'),
                             'video_frames.jsonl': sha(source / 'video_frames.jsonl'),
                             'signal_reference.mkv': sha(video)}
            if item['acquisition_sha256']['native_samples.jsonl'] != source_hashes['native_samples.jsonl'] or item['acquisition_sha256']['video_frames.jsonl'] != source_hashes['video_frames.jsonl'] or item['acquisition_sha256']['signal_reference.mkv'] != source_hashes['signal_reference.mkv']:
                raise ValueError('Saved source hashes differ')
            samples = rows(source / 'native_samples.jsonl')
            entry = next(i for i, r in enumerate(samples) if max(p[1] for p in r['native_body_xy_m']) >= -7)
            yellow = next(i for i, r in enumerate(samples) if r['observed_signal_state'] == 'yellow')
            red = next(i for i, r in enumerate(samples) if r['observed_signal_state'] == 'red')
            expected = {'yellow_warning_onset_frame': yellow,
                        'observed_signal_phase_at_entry': samples[entry]['observed_signal_state'],
                        'red_exhibition_onset_frame': red,
                        'full_body_intersection_entry_frame': entry,
                        'entry_to_red_margin_frames': red - entry}
            if sorted(expected) != item['measurement_keys'] or sorted(expected) != sorted(r['output_key'] for r in json.loads(contract.read_text())['requirements']):
                raise ValueError('Statutory measurement key coverage differs')
            for key, value in expected.items():
                measured = report['measurements'][key]
                if measured['value'] != value or measured['sources'] != source_hashes:
                    raise ValueError('Independent saved measurement differs: ' + key)
            if result['target_checks'][0]['measured'] != expected['observed_signal_phase_at_entry'] or result['measured_values']['entry_frame'] != entry:
                raise ValueError('Native result differs from independent source measurement')
            if report['synthetic_video_proof']['video_sha256'] != source_hashes['signal_reference.mkv'] or report['synthetic_video_proof']['decoded_frames'] != 480 or report['synthetic_video_proof']['original_carla_pixels_verified']:
                raise ValueError('Decoded synthetic pixel source differs')
    return {'passed': True, 'audited_bundles': 8, 'contract_outputs_per_bundle': 5,
            'missing_source_negatives': 8, 'wrong_video_negatives': 8,
            'wrong_join_negatives': 8,
            'synthetic_only': True,
            'summary_sha256': sha(summary_path)}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
