"""Derive an explicitly synthetic contrast probe from retained reference samples."""
import json
import shutil
from pathlib import Path

from native_finalize import finalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT/'.runtime-work/c201084-update102-finalizer-current-2'
DEST = ROOT/'.runtime-work/c201084-update104-contrast-source'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def build():
    if DEST.exists():
        raise ValueError('Use a fresh contrast source destination')
    DEST.mkdir(parents=True)
    config = json.loads((SOURCE/'config.json').read_text())
    config['case_suffix'] = 'contrast'
    config['case_id'] = HERE.name+'__contrast'
    config['selected_case_id'] = config['case_id']
    config['comparison_requested_value'] = False
    (DEST/'config.json').write_text(json.dumps(config, sort_keys=True, indent=2)+'\n')
    for name in ('acquisition-provenance.json', 'native-survey-readback.json',
                 'video_frames.jsonl', *(camera+'.mkv' for camera in CAMERAS)):
        shutil.copyfile(SOURCE/name, DEST/name)
    actors = []
    for line in (SOURCE/'native-actors.jsonl').read_text().splitlines():
        actor = json.loads(line)
        actor['ego_pose_xyz_m'][0] += 14
        for key in ('ego_body_vertices_xyz_m', 'following_body_vertices_xyz_m'):
            for vertex in actor[key]:
                vertex[0] += 14
        actors.append(actor)
    (DEST/'native-actors.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in actors))
    result = finalize(DEST, DEST/'analysis-report.json')
    return {'source': str(DEST.relative_to(ROOT)), 'result': result}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
