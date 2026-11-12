"""Physical entry traversal from saved originals; legal space sufficiency stays open."""
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon
from space_measure import analyze as measure_space

LIFECYCLE=('capture_finished','encoders_closed','restoration_verified',
           'native_exit','owner_released','saved_processing_started')


def validate_lifecycle(events):
    if tuple(events)!=LIFECYCLE:
        raise ValueError('saved processing began before Native exit and owner release')
    return True


def assess(scene_path,frames_path,source_kind='diagnostic'):
    paths=[Path(scene_path),Path(frames_path)]
    refs=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in paths if p.is_file()]
    status='unverified';realized={}
    if len(refs)==2:
        try:
            scene=json.loads(paths[0].read_text())
            frames=[json.loads(line) for line in paths[1].read_text().splitlines() if line.strip()]
            measured=measure_space(scene,frames)
            region=Polygon(scene['entry_region'])
            bodies=[Polygon(row['ego_footprint']) for row in frames]
            entered=any(body.intersects(region) for body in bodies[1:-1])
            before=not bodies[0].intersects(region)
            after=not bodies[-1].intersects(region)
            ordered=all(a['time_s']<b['time_s'] for a,b in zip(frames,frames[1:]))
            completed=source_kind=='native' and before and entered and after and ordered
            status='met' if completed else 'not_met'
            realized={'entry_frame':measured['entry']['frame'],'before_region':before,
                      'entered_region':entered,'after_region':after,'time_ordered':ordered}
        except (ValueError,KeyError,TypeError,json.JSONDecodeError):
            status='unverified'
    return {'physical_checks':{'maneuver':{'status':status,
            'method':'original full-body polygons traverse the source entry region with ordered time',
            'sources':refs}},'maneuver_completed':status=='met',
            'realized_observables':realized if status=='met' else {},
            'provenance_kind':source_kind,'legal_sufficiency':'unreviewed',
            'legal_obstruction':'unreviewed'}
