"""Project retained, explicitly authored scenario geometry into existing Core types.

This does not infer statutory governance from a nearby sign or a map waypoint.
The declaration and original-frame device inventory remain hashed evidence.
"""
import json
import hashlib
import math
from pathlib import Path
from .geometry import xy



def _verified_source(original, name, digest):
    if (not isinstance(name, str) or not name or Path(name).is_absolute()
            or '..' in Path(name).parts or not isinstance(digest, str)
            or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('Geometry verification requires a relative review/source path and SHA-256')
    root = Path(original).resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Geometry verification review/source is missing or outside original evidence')
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Geometry verification review/source hash mismatch: '+name)
    return path


def verification_review(original, verification):
    """Check the review and its declared sources; interpretation stays explicit."""
    if not isinstance(verification, dict) or not ({'review', 'sha256'} & verification.keys()):
        return None
    name, digest = verification.get('review'), verification.get('sha256')
    path = _verified_source(original, name, digest)
    if path.suffix.lower() == '.json':
        document = json.loads(path.read_text())
        sources = document.get('sources', {}) if isinstance(document, dict) else {}
        if not isinstance(sources, dict):
            raise ValueError('Geometry review sources must name files and SHA-256 values')
        for source, source_digest in sources.items():
            _verified_source(original, source, source_digest)
    return {'review': name, 'sha256': digest}


def verified_legends(original, verification):
    """Read source-bound legend readings from the existing physical review.

    ``regulatory_sign_legends`` contains assets and complete, recording-constant
    assemblies. An asset version is the SHA-256 of a retained revision source
    (which must bind the captured appearance, including dependencies); current
    installed bytes alone are not historical revision evidence. No built-in
    asset names or conditions defaults establish such a reading.
    """
    review = verification_review(original, verification)
    if review is None or Path(review['review']).suffix.lower() != '.json':
        return []
    document = json.loads((Path(original) / review['review']).read_text())
    legends = document.get('regulatory_sign_legends')
    if legends is None:
        return []
    if not isinstance(legends, dict):
        raise ValueError('Sign legend mapping must be an object')
    assets = {}
    for asset in legends.get('assets', []):
        key = (asset['asset_path'], asset['asset_version'], asset['code'])
        source = asset['revision_source']
        if (not isinstance(key[0], str) or not key[0].startswith('/Game/')
                or document.get('sources', {}).get(source) != key[1]):
            raise ValueError('Sign legend requires full asset identity and source-bound revision')
        _verified_source(original, source, key[1])
        conditions = asset['conditions']
        allowed = {'windows', 'min_occupancy', 'duration_limit', 'vehicle_class', 'when_children_present'}
        if not isinstance(conditions, dict) or set(conditions) - allowed:
            raise ValueError('Sign legend uses unsupported conditions')
        if (not isinstance(conditions.get('windows', []), list)
                or ('min_occupancy' in conditions and (type(conditions['min_occupancy']) is not int or conditions['min_occupancy'] < 0))
                or ('duration_limit' in conditions and (type(conditions['duration_limit']) not in (int, float) or not math.isfinite(conditions['duration_limit']) or conditions['duration_limit'] < 0))
                or ('vehicle_class' in conditions and not isinstance(conditions['vehicle_class'], str))
                or ('when_children_present' in conditions and type(conditions['when_children_present']) is not bool)):
            raise ValueError('Sign legend conditions have invalid types or values')
        for window in conditions.get('windows', []):
            if not isinstance(window, dict) or set(window) - {'weekdays', 'calendar_class', 'start_minute', 'end_minute'}:
                raise ValueError('Sign legend uses unsupported condition window')
            if (not isinstance(window.get('weekdays', []), list)
                    or any(type(day) is not int or not 0 <= day <= 6 for day in window.get('weekdays', []))
                    or ('calendar_class' in window and not isinstance(window['calendar_class'], str))
                    or any(type(window.get(field, default)) is not int or not 0 <= window.get(field, default) <= 1440
                           for field, default in [('start_minute', 0), ('end_minute', 1440)])):
                raise ValueError('Sign legend condition window has invalid types or values')
        if key in assets and assets[key] != conditions:
            raise ValueError('Conflicting asset legend conditions')
        assets[key] = conditions
    result = []
    for assembly in legends.get('assemblies', []):
        # Incomplete or variable assemblies remain unknown, even for known assets.
        if assembly.get('complete') is not True or assembly.get('constant') is not True:
            continue
        key = (assembly.get('asset_path'), assembly.get('asset_version'), assembly.get('code'))
        if key not in assets:
            continue
        for field in ('actor_id', 'native_name', 'position_m'):
            if field not in assembly:
                raise ValueError('Sign assembly requires original device identity and position')
        result.append(dict(assembly, conditions=assets[key]))
    return result


def conditions_for_sign(legends, observation, code, kind='regulatory_sign'):
    """Project one exact original-frame device join; None means unknown.

    Both fresh and saved callers use this join, before changing coordinate or
    device IDs. Ordinary stop/yield signs have no conditions projection.
    """
    import copy
    if kind not in {'regulatory_sign', 'zone_sign'}:
        return None
    matches = [entry for entry in legends
               if entry['actor_id'] == observation.get('actor_id')
               and entry['native_name'] == observation.get('native_name')
               and entry['position_m'] == observation.get('position_m')
               and entry['code'] == code]
    if not matches:
        return None
    conditions = matches[0]['conditions']
    if any(entry['conditions'] != conditions for entry in matches[1:]):
        raise ValueError('Conflicting complete sign assemblies')
    return copy.deepcopy(conditions)


def retained_review(evidence):
    """Use the same review contract with closed retained source files."""
    declaration = evidence.path('scenario_geometry.json')
    if declaration is None:
        return None
    data = json.loads(declaration.read_text())
    review = verification_review(declaration.parent, data.get('physical_verification'))
    if review is not None and evidence.path(review['review']) is None:
        raise ValueError('Geometry verification review is not bound to original evidence')
    return review


def apply(original, regions, polygons, devices):
    from shapely.geometry import Polygon
    path = Path(original)/'scenario_geometry.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if not data.get('source') or not data.get('physical_verification'):
        raise ValueError('Scenario geometry requires explicit provenance and physical verification')
    review = verification_review(original, data['physical_verification'])
    legends = verified_legends(original, data['physical_verification'])
    mapping = []
    def region(kind, vertices, **fields):
        boundary = [xy(v) for v in vertices]
        shape = Polygon(boundary)
        if not shape.is_valid or shape.area <= 0:
            raise ValueError('Invalid scenario reference polygon')
        # Merge the same physical region by kind and recorded geometry, not
        # aliases or overlapping words. Conflicting attributes require repair.
        for existing in regions:
            previous=polygons.get(existing['id'])
            if existing['kind']==kind and previous is not None and previous.equals(shape):
                for name,value in fields.items():
                    old=existing.get(name)
                    if old is not None and old!=value:raise ValueError('Conflicting canonical region attribute: '+name)
                    existing[name]=value
                mapping.append({'region_id':existing['id'],'kind':kind,'merged_existing':True})
                return existing['id']
        ident = max((r['id'] for r in regions), default=0)+1
        regions.append(dict(id=ident, kind=kind, boundary=boundary, **fields))
        polygons[ident] = shape
        mapping.append({'region_id':ident,'kind':kind})
        return ident
    roads=[]
    for road in data.get('directed_roadways', []):
        direction=xy(road['direction_xy'])
        if sum(v*v for v in direction)==0:
            raise ValueError('Scenario roadway requires a nonzero direction')
        kind='one_way_roadway' if road.get('one_way') else 'roadway'
        roads.append(region(kind,road['polygon'],lane={'direction':direction}))
    for vertices in data.get('prohibited_median_polygons', []):
        region('median_or_divider',vertices,opening=False)
    for vertices in data.get('median_opening_polygons', []):
        region('median_or_divider',vertices,opening=True)
    if data.get('intersection_polygon'):
        region('intersection',data['intersection_polygon'])
    # A custom map can use a sidewalk mesh to realize a median. Its verified
    # declared role replaces that renderer classification; it is not a second
    # pedestrian entity at the same place. Original native metadata is retained.
    median_ids=[m['region_id'] for m in mapping if m['kind']=='median_or_divider']
    replaced=[]
    for existing in list(regions):
        if existing['kind']!='sidewalk':continue
        shape=polygons.get(existing['id'])
        if shape is not None and any(polygons[r].covers(shape) for r in median_ids):
            replaced.append({'native_region_id':existing['id'],'native_kind':'sidewalk',
                             'canonical_role':'median_or_divider','reason':'Verified custom physical median realization'})
            regions.remove(existing);polygons.pop(existing['id'],None)
    signs=data.get('direction_sign_objects', [])
    if signs:
        samples=[json.loads(line) for line in (Path(original)/'scenario_rule_evidence.jsonl').read_text().splitlines() if line.strip()]
        if not samples:raise ValueError('Native sign projection requires original-frame observations')
        for sign in signs:
            ident=sign['id'];indices=sign['governs_roadway_indices']
            if not indices or any(not isinstance(i,int) or i<0 or i>=len(roads) for i in indices):
                raise ValueError('Explicit sign governance must name declared roadway indices')
            for sample in samples:
                obs=next((d for d in sample['value']['devices'] if d['actor_id']==ident),None)
                if not obs or obs.get('native_name')!=sign['native_name'] or obs.get('position_m')!=sign['position_m']:
                    raise ValueError('Native sign identity/geometry absent from an original tick')
            key=('environment',str(ident))
            if key in devices:raise ValueError('Duplicate native sign identity')
            devices[key]={'kind':'regulatory_sign','code':'one_way','position':xy(sign['position_m']), 'governs':[roads[i] for i in indices]}
            conditions = conditions_for_sign(legends, obs, 'one_way')
            if conditions is not None:
                devices[key]['conditions'] = conditions
    return {'native_role_replacements':replaced,'source':str(path),'declaration':data,'regions':mapping,
            **({'physical_verification_review':review} if review is not None else {}),
            'scope':'Explicit scenario geometry and authored governance; not an inferred legal boundary'}
