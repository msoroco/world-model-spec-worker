"""Read cited fire-station and road facts before Native acquisition."""
import hashlib
import json
import math
from pathlib import Path

FACTS=('station_identity','driveway_entrance','highway_boundary','activity_and_directions')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    path=Path(path).resolve()
    record=json.loads(path.read_text())
    if record.get('format')!='c229410-authority-context-v1':
        raise ValueError('Fire-station authority context format differs')
    if record.get('state')!='Nevada' or record.get('public_highway') is not True:
        raise ValueError('Cited Nevada public highway fact required')
    extent=record.get('entrance')
    if not isinstance(extent,dict) or any(type(extent.get(k)) not in (int,float) or not math.isfinite(extent[k]) for k in ('x_min_m','x_max_m','road_edge_y_m')):
        raise ValueError('Cited fire-station driveway extent required')
    if extent['x_min_m']>=extent['x_max_m'] or extent.get('road_side') not in ('north','south'):
        raise ValueError('Fire-station driveway side or extent invalid')
    if record.get('initial_activity') not in ('stopped','standing','parked'):
        raise ValueError('Cited initial stop/stand/park activity required')
    if record.get('exception_context') not in ('none','traffic_conflict','law','police_officer','official_device'):
        raise ValueError('Cited exception context required')
    reviews=record.get('fact_reviews')
    if not isinstance(reviews,dict) or any(reviews.get(name) is not True for name in FACTS):
        raise ValueError('Independent review conclusion required for each authority fact')
    sources=record.get('sources')
    if not isinstance(sources,dict) or set(sources)!=set(FACTS):
        raise ValueError('Four cited authority sources required')
    source_paths={}
    for name in FACTS:
        item=sources[name]
        if not isinstance(item,dict) or not item.get('citation') or not item.get('path') or not item.get('sha256'):
            raise ValueError('Incomplete cited source: '+name)
        relative=Path(item['path'])
        if relative.is_absolute():
            raise ValueError('Authority source path must be relative: '+name)
        source=(path.parent/relative).resolve()
        if path.parent not in source.parents or not source.is_file() or sha(source)!=item['sha256']:
            raise ValueError('Authority source missing or changed: '+name)
        source_paths[name]=source
    return {'record':record,'manifest_path':path,'manifest_sha256':sha(path),'source_paths':source_paths}
