"""Audit all 21 fallback pairings against draft-hash synthetic sources."""
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair
from prove_body_geometry_draft_primary_comparisons import source as primary_source


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(row):
    bundle = json.loads((ROOT / row['construction']).read_text())
    return json.loads(next(item['content'] for item in bundle['files']
                           if item['path'] == 'config.json'))


def main():
    manifest_path = ROOT / 'body-geometry-all-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    indexed_cases = {row['case_id']: row for row in manifest['cases']}
    receipt_path = ROOT / 'body-geometry-draft/fallback-source-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('manifest_sha256') != digest(manifest_path)
            or receipt.get('generator_sha256') != digest(
                ROOT / 'generate_body_geometry_draft_fallback_sources.py')
            or receipt.get('physical_fallback_motion_proven') is not False
            or len(receipt['sources']) != 24):
        raise ValueError('Draft fallback projection receipt changed')
    indexed = {(row['case_id'], row['candidate_id']): row
               for row in receipt['sources']}
    if len(indexed) != 24:
        raise ValueError('Duplicate fallback projections')

    def candidate_source(case_id, candidate_id):
        if candidate_id == 'primary':
            return primary_source(case_id)
        entry = indexed_cases[case_id]
        selected = next(row for row in entry['candidates']
                        if row['id'] == candidate_id)
        proof = indexed[(case_id, candidate_id)]
        path = REPO / proof['path']
        if (proof['construction_sha256'] != selected['construction_sha256']
                or proof['sha256'] != digest(path)
                or proof['frames'] != 900
                or proof['source_specification_sha256'] != digest(
                    REPO / proof['source_specification'])):
            raise ValueError('Fallback source or draft construction changed')
        changed = {key: value for key, value in config(selected).items()
                   if config(entry).get(key) != value and
                   key not in ('selected_case_id', 'supported_case_ids')}
        if changed != proof['changed_config']:
            raise ValueError('Fallback source changed config dimension')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        expected = {'candidate_id': candidate_id,
                    'construction_sha256': selected['construction_sha256'],
                    'changed_config': changed, 'physical_motion_proven': False}
        if len(rows) != 900 or any(row.get('diagnostic_projection') != expected
                                   for row in rows):
            raise ValueError('Fallback source lacks draft-bound projection')
        return path

    pairings = [json.loads(line) for line in
                (ROOT / 'all-comparison-audit.log').read_text().splitlines()]
    pairings = [row for row in pairings
                if (row['left_candidate'], row['right_candidate'])
                != ('primary', 'primary')]
    if (len(pairings) != 21 or
            Counter(row['comparison_id'] for row in pairings) !=
            {key: 3 for key in ('body_gap', 'ego_speed', 'lead_speed',
                                'lead_braking', 'wet_surface', 'following_end',
                                'queued_traffic')}):
        raise ValueError('Expected seven groups of three fallback pairings')
    with tempfile.TemporaryDirectory(prefix='c101303-geometry-fallback-comparison-',
                                     dir=REPO / '.runtime-work') as temporary:
        context = Path(temporary)
        shutil.copyfile(manifest_path, context / 'execution-manifest.json')
        shutil.copyfile(ROOT / 'case-plan.json', context / 'case-plan.json')
        for entry in manifest['cases']:
            for row in [entry] + entry['candidates']:
                original = ROOT / row['construction']
                if digest(original) != row['construction_sha256']:
                    raise ValueError('Draft construction changed')
                target = context / row['construction']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
        results = []
        for pair in pairings:
            left_id, right_id = pair['case_ids']
            left_candidate = pair['left_candidate']
            right_candidate = pair['right_candidate']
            left = candidate_source(left_id, left_candidate)
            right = candidate_source(right_id, right_candidate)
            result = audit_pair(context, pair['comparison_id'], left, right,
                                left_candidate=None if left_candidate == 'primary'
                                else left_candidate,
                                right_candidate=None if right_candidate == 'primary'
                                else right_candidate)
            if (result['frames'] != 900 or
                    result['changed_config_keys'] != pair['changed_config_keys']):
                raise ValueError('Fallback comparison dimension or duration changed')
            results.append(result)
            print(pair['comparison_id'], left_candidate, right_candidate,
                  result['frames'], flush=True)
    output = ROOT / 'body-geometry-draft/fallback-comparison-proof.json'
    output.write_text(json.dumps({'manifest_sha256': digest(manifest_path),
                                  'projection_receipt_sha256': digest(receipt_path),
                                  'audit_sha256': digest(ROOT / 'comparison_audit.py'),
                                  'comparison_count': len(results),
                                  'comparisons': results,
                                  'physical_fallback_motion_proven': False},
                                 indent=2) + '\n')
    print('fallback comparisons passed', len(results))


if __name__ == '__main__':
    main()
