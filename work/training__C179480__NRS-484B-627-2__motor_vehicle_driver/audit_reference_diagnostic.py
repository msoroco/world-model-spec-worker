"""Independently bind one pinned diagnostic compatibility and saved revision."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name+'__reference'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(attempt, saved):
    attempt = Path(attempt).resolve()
    saved = Path(saved).resolve()
    manifest = read(HERE/'draft-reference-compatibility-manifest.json')
    entry = manifest['cases'][0]
    compatibility = read(attempt/'compatibility.json')
    receipt = read(saved/'v0001/processing.json')
    require(len(manifest['cases']) == 1 and entry['case_id'] == CASE,
            'Diagnostic manifest selects another case')
    require(entry['construction_sha256'] == sha(HERE/entry['construction']),
            'Selected construction changed')
    require(compatibility['passed'] is True and compatibility['case_id'] == CASE
            and compatibility['candidate_id'] == 'primary'
            and compatibility['construction_sha256'] == entry['construction_sha256']
            and compatibility['runtime_manifest_sha256'] ==
            manifest['runtime_manifest_sha256'], 'Pinned compatibility identity differs')
    require(compatibility['fixture_recipe_sha256'] ==
            sha(ROOT/entry['fixture_recipe']) and
            compatibility['measurement_contract_sha256'] ==
            sha(HERE/entry['measurement_contract']), 'Fixture/measurement binding differs')
    require({'selected_measurements','negative_case_source','four_camera_sources',
             'native_validation','lean_decoder','render','final_decode'} <=
            set(compatibility['checks']), 'Pinned compatibility checks incomplete')
    require(compatibility['negative_removed'] == 'native-map-readback.json'
            and compatibility['negative_error_contains'] in
            (attempt/'negative-analysis.log').read_text(),
            'Missing-map negative did not reject')
    original = read(attempt/'result.json')
    stage = saved/'v0001/analysis'
    reprocessed = read(stage/'result.json')
    require(receipt['passed'] is True and receipt['recorded_only'] is True
            and receipt['originals_preserved'] is True
            and receipt['missing_evidence'] is False
            and receipt['timestamp_joins'] == {'frames':600,'passed':True,
                                               'missing_original_trace_or_map':False}
            and receipt['candidate_id'] == 'primary'
            and receipt['analysis_revision']['construction_sha256'] ==
            entry['construction_sha256'], 'Saved revision incomplete')
    require(receipt['result_sha256'] == sha(stage/'result.json')
            and all(sha(attempt/path) == checksum for path, checksum in
                    receipt['original_source_hashes'].items()),
            'Saved revision changed source or result')
    for result, folder in ((original,attempt),(reprocessed,stage)):
        traces = [read_line for read_line in
                  (folder/'trace.jsonl').read_text().splitlines() if read_line]
        require(len(traces) == 600 and len(result['video_references']) == 4
                and result['provenance_kind'] == 'synthetic_fixture'
                and result['accepted'] is False
                and result['maneuver_completed'] is False
                and result['legal_verdict_claimed'] is False,
                'Diagnostic result overclaims acceptance or omits sources')
        require(all(json.loads(line)['speed_provenance'] ==
                    'synthetic_native_sample' for line in traces),
                'Invented speed claimed original provenance')
    report = {
        'format':'c179480-reference-diagnostic-delivery-audit-v1',
        'case_id':CASE, 'candidate_id':'primary',
        'compatibility_sha256':sha(attempt/'compatibility.json'),
        'saved_processing_sha256':sha(saved/'v0001/processing.json'),
        'construction_sha256':entry['construction_sha256'],
        'recipe_sha256':sha(ROOT/entry['fixture_recipe']),
        'source_frames':600,'source_cameras':4,
        'positive_compatibility_passed':True,
        'negative_missing_map_rejected':True,
        'recorded_only_saved_passed':True,
        'provenance_kind':'synthetic_fixture',
        'physical_acceptance_claimed':False,
        'legal_acceptance_claimed':False,
        'scope':'draft primary diagnostic only; canonical case/fallbacks unproved',
    }
    path=HERE/'update089-reference-delivery-audit.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    return {'audit_sha256':sha(path),'passed':True}


if __name__ == '__main__':
    print(json.dumps(audit(
        ROOT/'.runtime-work/c179480-update089/reference-primary-compatibility-v9',
        ROOT/'.runtime-work/c179480-update089/reference-primary-saved-v9'),
        sort_keys=True))
