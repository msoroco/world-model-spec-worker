"""Independently bind C111331's eight exact synthetic portable receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pickle

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
REPO = HERE.parents[2]
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = digest(HERE / 'package-manifest.json')
    checked = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE / 'portable-receipts' / case / candidate
            source = HERE / 'synthetic-saved' / case / candidate
            summary = read(folder / 'summary.json')
            receipt = read(folder / 'compatibility.json')
            report = read(folder / 'analysis-report.json')
            result = read(folder / 'result.json')
            decode = read(folder / 'final-decode.json')
            cid = ASSIGNMENT + '__' + case
            assert summary['format'] == 'c111331-exact-synthetic-portable-v1'
            assert summary['case_id'] == receipt['case_id'] == report['case_id'] == result['case_id'] == cid
            assert summary['candidate_id'] == receipt['candidate_id'] == candidate
            assert summary['manifest_sha256'] == manifest
            assert summary['fixture_native_sha256'] == digest(source / 'native_samples.jsonl')
            assert summary['fixture_map_sha256'] == digest(source / 'video_frames.jsonl')
            fixture = REPO / summary['fixture_runtime_relative']
            assert digest(fixture / 'capture/manifest.json') == summary['fixture_manifest_sha256']
            source_rows = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
            graph_rows = [json.loads(line) for line in (fixture / 'capture/native/frames.jsonl').read_text().splitlines()]
            evidence_rows = [json.loads(line) for line in (fixture / 'capture/evidence.jsonl').read_text().splitlines()]
            assert len(source_rows) == len(graph_rows) == len(evidence_rows) == 480
            for index, (native, graph_row, evidence) in enumerate(zip(source_rows, graph_rows, evidence_rows)):
                frame = native['native_frame']
                assert graph_row['frame'] == evidence['original_frame'] == evidence['replay_frame'] == frame
                graph = pickle.loads((fixture / 'capture/native' / graph_row['base']).read_bytes())
                signal = graph.nodes['signal_601']
                assert signal['light_state'] == 'TrafficLightState.' + native['observed_signal_state'].capitalize()
                assert signal['observed_governs'] == [[1, 0, -1]]
                assert graph.graph['observed_evidence']['frame'] == frame
                assert evidence['ego']['position_m'][:2] == native['native_center_xy_m']
                assert evidence['ego']['heading_deg'] == native['native_yaw_deg']
                assert graph_row['time_s'] == native['time_s']
            assert receipt['fixture_manifest']['native_samples.jsonl'] == summary['fixture_native_sha256']
            assert receipt['fixture_manifest']['video_frames.jsonl'] == summary['fixture_map_sha256']
            assert receipt['fixture_manifest']['capture/manifest.json'] == summary['fixture_manifest_sha256']
            assert summary['positive_receipt_sha256'] == digest(folder / 'compatibility.json')
            assert summary['positive_log_sha256'] == digest(folder / 'portable-analysis.log')
            assert summary['final_decode_sha256'] == digest(folder / 'final-decode.json')
            assert summary['negative_log_sha256'] == digest(folder / 'negative-analysis.log')
            assert receipt['passed'] is True and CHECKS.issubset(receipt['checks'])
            assert receipt['scope'] == 'diagnostic software compatibility only'
            assert report['selected'] is False and report['draft_only'] is True
            assert result['accepted'] is False and result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert decode['passed'] is True and decode['frames'] == 480
            assert summary['synthetic_only'] is True and summary['native_or_original_pixels_claimed'] is False
            assert summary['negative_error'] in (folder / 'negative-analysis.log').read_text()
            checked.append({'case_id': cid, 'candidate_id': candidate,
                            'summary_sha256': digest(folder / 'summary.json')})
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        ref = read(HERE / 'portable-receipts/reference' / candidate / 'analysis-report.json')
        contrast = read(HERE / 'portable-receipts/contrast' / candidate / 'analysis-report.json')
        a, b = ref['measurements'], contrast['measurements']
        assert a['full_body_intersection_entry_frame']['value'] == b['full_body_intersection_entry_frame']['value']
        assert a['observed_signal_phase_at_entry']['value'] == 'yellow'
        assert b['observed_signal_phase_at_entry']['value'] == 'red'
        assert a['red_exhibition_onset_frame']['value'] > a['full_body_intersection_entry_frame']['value']
        assert b['red_exhibition_onset_frame']['value'] < b['full_body_intersection_entry_frame']['value']
    output = {'format': 'c111331-exact-synthetic-portable-audit-v1',
              'manifest_sha256': manifest, 'candidate_receipts': checked,
              'positive_count': 8, 'missing_source_negative_count': 8,
              'controlled_pair_count': 4,
              'scope': 'unselected synthetic diagnostic compatibility only'}
    path = HERE / 'portable-audit-summary.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'summary_sha256': digest(path),
                      'positive_count': 8, 'negative_count': 8}, sort_keys=True))


if __name__ == '__main__':
    audit()
