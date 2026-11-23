"""Independent current-runtime synthetic paired-source and saved-path audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(HERE / 'current-diagnostic-manifest.json')
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    assert manifest['runtime_manifest_sha256'] == runtime_sha
    data = []
    for suffix, tag, expected in [('condition_a', 'a5', 10.0), ('condition_b', 'b1', 25.0)]:
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith(suffix))
        recipe = HERE / 'current-fixture' / (suffix + '-recipe.json')
        construction = HERE / entry['construction']
        contract = HERE / entry['measurement_contract']
        compat = ROOT / ('.runtime-work/c102304-current-compat-' + tag)
        saved = ROOT / ('.runtime-work/c102304-current-saved-' + tag + '/v0001')
        c = read(compat / 'compatibility.json')
        s = read(saved / 'processing.json')
        report = read(compat / 'analysis-report.json')
        measured = report['measurements']['moving_following_interval']['value']
        assert entry['construction_sha256'] == sha(construction)
        assert c['passed'] is True and c['case_id'] == entry['case_id']
        assert c['candidate_id'] == 'primary'
        assert c['runtime_manifest_sha256'] == runtime_sha
        assert c['construction_sha256'] == sha(construction)
        assert c['fixture_recipe_sha256'] == sha(recipe)
        assert c['measurement_contract_sha256'] == sha(contract)
        assert c['negative_removed'] == 'native_samples.jsonl'
        assert c['negative_error_contains'] in (compat/'negative-analysis.log').read_text()
        assert c['negative_log_sha256'] == sha(compat/'negative-analysis.log')
        assert s['passed'] is True and s['recorded_only'] is True
        assert s['case_id'] == entry['case_id'] and s['candidate_id'] == 'primary'
        assert s['analysis_revision']['construction_sha256'] == sha(construction)
        assert s['analysis_revision']['runtime_manifest_sha256'] == runtime_sha
        assert s['originals_preserved'] is True
        assert s['timestamp_joins']['passed'] is True and s['timestamp_joins']['frames'] == 900
        assert s['final_video_checks']['passed'] is True and s['final_video_checks']['frames'] == 900
        assert s['physical_acceptance_claimed'] is False and s['legal_acceptance_claimed'] is False
        assert measured['median_bumper_gap_m'] == expected
        assert measured['following_duration_s'] == 45.0
        samples = [json.loads(line) for line in (HERE/'current-fixture'/suffix/'native_samples.jsonl').read_text().splitlines()]
        assert len(samples) == 900
        data.append((samples, {'case_id': entry['case_id'], 'measured_gap_m': expected,
                               'recipe_sha256': sha(recipe), 'construction_sha256': sha(construction),
                               'compatibility_sha256': sha(compat/'compatibility.json'),
                               'saved_sha256': sha(saved/'processing.json')}))
    for a, b in zip(data[0][0], data[1][0]):
        assert a['ego'] == b['ego']
        assert a['native_frame'] == b['native_frame'] and a['time_s'] == b['time_s']
        assert a['lead']['native_road_id'] == b['lead']['native_road_id']
        assert a['lead']['native_lane_id'] == b['lead']['native_lane_id']
        assert a['lead']['native_forward_xy'] == b['lead']['native_forward_xy']
        assert a['lead']['speed_mps'] == b['lead']['speed_mps']
        for pa, pb in zip(a['lead']['native_body_xy_m'], b['lead']['native_body_xy_m']):
            assert abs((pb[0]-pa[0])-15.0) < 1e-8 and abs(pb[1]-pa[1]) < 1e-8
    receipt = {'format': 'c102304-current-synthetic-comparison-audit',
               'comparison_id': HERE.name + '__selected_ccee258c__comparison',
               'frames_per_case': 900, 'duration_s': 45,
               'fixed_ego_context_and_lead_speed': True,
               'lead_body_x_shift_m': 15.0,
               'cases': [item[1] for item in data],
               'runtime_manifest_sha256': runtime_sha,
               'source_status': 'synthetic_diagnostic_only',
               'physical_or_legal_acceptance_claimed': False}
    (HERE/'current-comparison-proof.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
