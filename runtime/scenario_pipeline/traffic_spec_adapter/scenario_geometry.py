"""Project retained, explicitly authored scenario geometry into existing Core types.

This does not infer statutory governance from a nearby sign or a map waypoint.
The declaration and original-frame device inventory remain hashed evidence.
"""
import json
from pathlib import Path
from .geometry import xy


def apply(original, regions, polygons, devices):
    from shapely.geometry import Polygon
    path = Path(original)/'scenario_geometry.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if not data.get('source') or not data.get('physical_verification'):
        raise ValueError('Scenario geometry requires explicit provenance and physical verification')
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
    return {'native_role_replacements':replaced,'source':str(path),'declaration':data,'regions':mapping,
            'scope':'Explicit scenario geometry and authored governance; not an inferred legal boundary'}
