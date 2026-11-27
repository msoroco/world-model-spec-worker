"""Run four synthetic saved-only electric paths and source-negative controls."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE / 'native'))
from electric_finalize import finalize
from electric_asset import review_digest


def fixture(kind, behavior):
    attempt = ROOT / '.runtime-work/c230207-electric-finalize' / kind / behavior
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / 'diagnostic-source' / behavior, attempt)
    construction = json.loads((HERE / 'draft-mounted-sidewalk' / behavior /
                               'primary/construction.json').read_text())
    ordinary_config = next(row['content'] for row in construction['files']
                           if row['path'] == 'config.json')
    (attempt / 'config.json').write_text(ordinary_config)
    shutil.copyfile(HERE / 'draft-mounted-sidewalk' / behavior /
                    'measurement-contract.json', attempt / 'measurement-contract.json')
    source_root = ROOT / '.runtime-work/c230207-electric-sources'
    source_root.mkdir(parents=True, exist_ok=True)
    source = source_root / (kind + '.txt')
    source.write_text('Synthetic review and asset source fixture only.\n')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    blueprint = 'vehicle.reviewed.' + ('ebike' if kind == 'electric_bicycle' else 'escooter')
    case_id = HERE.name + '__' + kind + '_' + behavior
    review = {'machine_class': kind, 'blueprint_id': blueprint,
              'source_kind': 'synthetic_test_only',
              'source_refs': [{'path': source.name, 'sha256': digest}]}
    config = json.loads((attempt / 'config.json').read_text())
    config.update(case_id=case_id, selected_case_id=case_id,
                  supported_case_ids=[case_id], case={'case_id': case_id},
                  rider_class=kind, machine_class=kind,
                  electric_asset_review=review,
                  electric_asset_source_root=str(source_root))
    (attempt / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    contract = json.loads((attempt / 'measurement-contract.json').read_text())
    contract['case_id'] = case_id
    (attempt / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    context = json.loads((attempt / 'restriction-context.json').read_text())
    context.update(rider_class=kind, blueprint_id=blueprint,
                   electric_asset_binding={
                       'machine_class': kind, 'blueprint_id': blueprint,
                       'native_actor_id': 42, 'classification_review_bound': True,
                       'review_source_sha256': {source.name: digest},
                       'review_sha256': review_digest(review),
                       'original_class_pixels_verified': False})
    (attempt / 'restriction-context.json').write_text(json.dumps(context, indent=2) + '\n')
    rows = [json.loads(line) for line in (attempt / 'bicycle-poses.jsonl').read_text().splitlines()]
    for row in rows:
        row.update(machine_class=kind, rider_blueprint_id=blueprint,
                   rider_actor_id=42, electric_asset_blueprint_id=blueprint)
    (attempt / 'bicycle-poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return attempt, source


def main():
    reports = []
    for kind in ('electric_bicycle', 'electric_scooter'):
        for behavior in ('walk_cycle', 'mounted_sidewalk'):
            attempt, _ = fixture(kind, behavior)
            report = finalize(attempt, attempt / 'electric-analysis-report.json')
            result = json.loads((attempt / 'result.json').read_text())
            assert report['electric_asset_binding']['machine_class'] == kind
            assert result['diagnostic_fixture'] is True
            assert report['physical_acceptance_claimed'] is False
            assert result['target_checks'][0]['physical_cause_confirmed'] is False
            reports.append({'case_id': report['case_id'],
                            'source_count': len(report['source_hashes'])})
    attempt, source = fixture('electric_scooter', 'mounted_sidewalk')
    source.write_text('Changed source fixture.\n')
    try:
        finalize(attempt, attempt / 'electric-analysis-report.json')
    except ValueError as error:
        assert 'Original electric asset source changed' in str(error), str(error)
    else:
        raise AssertionError('Stale electric asset source accepted')
    attempt, _ = fixture('electric_bicycle', 'walk_cycle')
    (attempt / 'restriction-context.json').unlink()
    try:
        finalize(attempt, attempt / 'electric-analysis-report.json')
    except FileNotFoundError:
        pass
    else:
        raise AssertionError('Missing original electric context accepted')
    return {'passed': True, 'fixture_kind': 'synthetic_native_sample',
            'exact_case_count': len(reports), 'cases': reports,
            'negative_stale_asset_source': True,
            'negative_missing_context': True,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
