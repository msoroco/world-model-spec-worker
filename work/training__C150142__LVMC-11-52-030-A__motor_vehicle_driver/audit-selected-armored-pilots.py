"""Recompute source facts for the four selected armored CPU pilot cases."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from delivery_audit import validate_exception_measurement


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    cases = ('armored_car_signed_business', 'armored_car_signed_no_business',
             'armored_car_unsigned_business', 'armored_car_unsigned_no_business')
    records = []
    for slug in cases:
        case = ROOT.name + '__' + slug
        receipt = ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-v1.json')
        if slug == 'armored_car_signed_business':
            proofs = [ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-v1.json'),
                      ROOT / ('selected-' + slug + '-four-candidate-proof-pilot-fallbacks-v1.json')]
        else:
            proofs = [receipt]
        entries = [row for proof in proofs for row in json.loads(proof.read_text())['records']]
        if [row['candidate_id'] for row in entries] != [
                'primary', 'fallback1', 'fallback2', 'fallback3'] or any(
                row['case_id'] != case or row['source_kind'] != 'synthetic_native_sample' or
                row['saved_frames'] != 361 or row['physical_acceptance_claimed']
                for row in entries):
            raise ValueError('Armored four-candidate pilot proof incomplete: ' + slug)
        if len({row['manifest_sha256'] for row in entries}) != 1:
            raise ValueError('Armored pilot proof used mixed manifests: ' + slug)
        for row in entries:
            candidate = row['candidate_id']
            path = REPO / '.runtime-work' / (
                'c150142-selected-' + slug + '-' + candidate + '-' +
                ('pilot-v1' if candidate == 'primary' or slug != 'armored_car_signed_business'
                 else 'pilot-fallbacks-v1') + '-result/v0001/analysis')
            measured = validate_exception_measurement(path, plan, case,
                                                       'synthetic_native_sample')
            if measured['frames'] != 361 or measured['legal_verdict'] is not None:
                raise ValueError('Armored synthetic source audit differs: ' + slug)
            records.append({'case_id': case, 'candidate_id': candidate,
                            'analysis_report_sha256': sha(path / 'analysis-report.json'),
                            'result_sha256': sha(path / 'result.json'),
                            'stationary_duration_s': measured['stationary_duration_s'],
                            'recorded_activity_names': measured['recorded_activity_names'],
                            'source_kind': 'synthetic_native_sample',
                            'original_native_observed': False})
    target = ROOT / 'selected-armored-pilot-source-audit-v1.json'
    target.write_text(json.dumps({'format': 'selected-armored-source-audit-v1',
                                  'records': records, 'original_native_observed': False,
                                  'physical_acceptance_claimed': False}, indent=2) + '\n')
    print(json.dumps({'candidate_sources_audited': len(records),
                      'receipt': target.relative_to(REPO).as_posix()}))


if __name__ == '__main__':
    main()
