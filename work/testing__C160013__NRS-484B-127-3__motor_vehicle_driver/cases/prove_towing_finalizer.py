"""Run the towing saved finalizer on a fresh source-bound diagnostic attempt."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from caravan_towing_finalizer import finalize


def main():
    source = REPO / '.runtime-work/c160013-wide-compat-v11'
    materialized = REPO / '.runtime-work/c160013-towing-draft-offline'
    stage = REPO / '.runtime-work/c160013-towing-finalizer-fixture'
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(materialized, stage)
    names = ('road_context.json', 'caravan_context.json', 'video_frames.jsonl',
             'trace.jsonl', 'business_district_source.txt',
             'caravan_membership_source.txt', 'route_source.txt', 'lane_source.txt',
             'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
    for name in names:
        shutil.copyfile(source / name, stage / name)
    shutil.copytree(source / 'capture', stage / 'capture', dirs_exist_ok=True)
    design = (stage / 'towing_design_source.txt').read_bytes()
    context = json.loads((stage / 'road_context.json').read_text())
    relationship = {'drawing_actor_id': 1, 'drawn_actor_id': 8,
                    'drawn_unit_has_motive_power': False,
                    'towing_design_source_sha256': hashlib.sha256(design).hexdigest()}
    data = (json.dumps(relationship, sort_keys=True) + '\n').encode()
    (stage / 'towing-relationship.json').write_bytes(data)
    context['towing_relationship_source'] = {
        'path': 'towing-relationship.json', 'sha256': hashlib.sha256(data).hexdigest(),
        'review_status': 'reviewed_native_relationship'}
    context['towing_design_source'] = {'path': 'towing_design_source.txt',
                                       'sha256': hashlib.sha256(design).hexdigest()}
    (stage / 'road_context.json').write_text(json.dumps(context) + '\n')
    rows = []
    for line in (source / 'caravan_history.jsonl').read_text().splitlines():
        row = json.loads(line)
        powered = next(member for member in row['caravan_members'] if member['actor_id'] == 1)
        row['drawn_units'] = [{'actor_id': 8, 'blueprint_id': 'static.prop.diagnostic_trailer',
                               'body_vertices_xy_m': [[x - 4, y] for x, y in powered['body_vertices_xy_m']]}]
        row['towing_relationship'] = {'drawing_actor_id': 1, 'drawn_actor_id': 8}
        rows.append(row)
    (stage / 'caravan_history.jsonl').write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                                    for row in rows))
    output = stage / 'towing-analysis-report.json'
    analysis = finalize(stage, output)
    result = json.loads((stage / 'result.json').read_text())
    assert output.is_file() and result['case_id'] == analysis['case_id']
    assert analysis['source_report']['original_frames'] == 900
    assert analysis['legal_verdict_asserted'] is False
    assert len(result['recording_evidence']) >= 8
    analysis_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    (stage / 'result.json').unlink()
    output.unlink()
    shutil.rmtree(stage / 'channels')
    (stage / 'towing_design_source.txt').write_text('changed design\n')
    try:
        finalize(stage, output)
    except ValueError as error:
        assert 'Changed original towing design source' in str(error)
    else:
        raise AssertionError('Changed original towing design accepted')
    print(json.dumps({'format': 'worker-towing-finalizer-diagnostic-proof',
                      'case_id': result['case_id'], 'original_frames': 900,
                      'recording_channels': len(result['recording_evidence']),
                      'physical_acceptance_claimed': False,
                      'legal_verdict_asserted': False,
                      'changed_towing_design_rejected': True,
                      'analysis_sha256': analysis_hash}, sort_keys=True))


if __name__ == '__main__':
    main()
