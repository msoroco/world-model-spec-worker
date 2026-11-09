"""Cheap static-map checks and removal of the retired grade-only overlays.

No all-pairs geometry test: the retired producer has a precise 300-strip
signature. A strip is removable only under a recorded containing roadway and
when it has no non-occupancy reference. Physical evidence stays in the archive.
"""
import json
from functools import lru_cache


def roadway_intervals(road, geometries, start, end):
    """Coalesce consecutive native segments with the same recorded properties."""
    from .geometry import reference
    result = []
    elevations = road.findall('./elevationProfile/elevation')
    for g in geometries:
        a = max(start, float(g.attrib['s']))
        b = min(end, float(g.attrib['s']) + float(g.attrib['length']))
        if b <= a:
            continue
        values = {'curvature': abs(reference(g, (a+b)/2)[3])}
        active = [e for e in elevations if float(e.attrib['s']) <= a+1e-9]
        breaks = [e for e in elevations if a < float(e.attrib['s']) < b]
        if active and not breaks and all(float(active[-1].attrib.get(k, 0)) == 0 for k in 'cd'):
            values['grade'] = float(active[-1].attrib.get('b', 0))
        if result and result[-1][1] == a and result[-1][2] == values:
            result[-1] = (result[-1][0], b, values)
        else:
            result.append((a, b, values))
    return result


def boundary_key(points):
    points = [tuple(p) for p in points]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if not points:
        return ()
    # Starting vertex and winding are representation choices, not new roads.
    start = min(range(len(points)), key=points.__getitem__)
    forward = points[start:] + points[:start]
    reverse = [forward[0]] + list(reversed(forward[1:]))
    return tuple(min(forward, reverse))


def grade_strips(regions):
    result = []
    for r in regions:
        if r.get('kind') != 'roadway' or 'grade' not in r:
            continue
        if set(r) - {'id', 'kind', 'boundary', 'grade', 'unobserved_kinds', 'sight_distance', 'lane'}:
            continue
        if r.get('lane'):
            continue
        b = r.get('boundary', [])
        if len(b) != 4:
            continue
        xs, ys = sorted({p[0] for p in b}), sorted({p[1] for p in b})
        if (len(xs) == len(ys) == 2 and ys == [-12, 12]
                and xs[1] - xs[0] == 2 and 450 <= xs[0] < 1050
                and set(map(tuple, b)) == {(x, y) for x in xs for y in ys}):
            result.append(r)
    if {min(p[0] for p in r['boundary']) for r in result} != set(range(450, 1050, 2)):
        return []
    return result


@lru_cache(maxsize=32)
def _check(encoded):
    roads = json.loads(encoded)
    seen = set()
    for r in roads:
        key = (r['kind'], boundary_key(r.get('boundary', [])))
        if key[1] and key in seen:
            raise ValueError('Duplicate roadway geometry; use one physical roadway')
        seen.add(key)
    if grade_strips(roads):
        raise ValueError('Retired 300-strip grade overlay; attach properties to physical roadways')


def validate_map(regions):
    """Check only roadway data; each distinct static map is checked once."""
    roads = []
    for r in regions:
        if r.get('kind') not in ('roadway', 'one_way_roadway'):
            continue
        # Only geometry and field presence affect this structural check. A
        # changing legacy sight scalar must not trigger a new map audit.
        value = {k: (v if k in ('id', 'kind', 'boundary') else 0)
                 for k, v in r.items() if k != 'unobserved_kinds'}
        if 'lane' in r:
            value['lane'] = {'present': True} if r['lane'] else {}
        roads.append(value)
    _check(json.dumps(roads, sort_keys=True, separators=(',', ':')))


def protected_regions(scene):
    """Local governance/entrance/intention scope cannot become a whole road."""
    result = set()
    for r in scene.get('structures', []):
        for k in ('ways', 'entrance_of'):
            result.update(r.get(k) or [])
        lane = r.get('lane') or {}
        for k in ('left', 'right', 'enters_intersection'):
            if lane.get(k) is not None:
                result.add(lane[k])
        result.update(lane.get('leads_to') or [])
    for d in scene.get('devices', []):
        result.update(d.get('governs') or [])
    result.update(i['target'] for i in scene.get('intents', []))
    for u in scene.get('users', []):
        result.update(w for w, _ in u.get('sight_along_way') or [])
    return result


def compatible_properties(left,right):
    """Union measured complementary fields; conflicting observations stay separate."""
    import copy
    result=copy.deepcopy(left)
    for key,value in right.items():
        if key in ('id','boundary'):continue
        if key=='unobserved_kinds':
            result[key]=sorted(set(result.get(key,[]))|set(value))
        elif key not in result or result[key] is None:
            result[key]=copy.deepcopy(value)
        elif value is None:continue
        elif isinstance(value,dict) and isinstance(result[key],dict):
            combined=compatible_properties(result[key],value)
            if combined is None:return None
            result[key]=combined
        elif result[key]!=value:return None
    return result


def consolidate(scene, identities=None):
    """Return a corrected copy and a receipt; never discard scoped references."""
    from .compatibility import remap_regions
    from shapely.geometry import Polygon
    regions = scene.get('structures', [])
    strips = grade_strips(regions)
    replacements = {}
    property_merges=[]
    issues = []
    if strips:
        strip_ids = {r['id'] for r in strips}
        protected = protected_regions(scene) & strip_ids
        if protected:
            issues.append('Grade strips have scoped references; reconstruction needed')
        else:
            candidates = []
            extent = Polygon([[450, -12], [1050, -12], [1050, 12], [450, 12]])
            for r in regions:
                if r.get('kind') != 'roadway' or r['id'] in strip_ids or not r.get('boundary'):
                    continue
                p = Polygon(r['boundary'])
                if p.is_valid and p.covers(extent):
                    candidates.append(r)
            if len(candidates) == 1:
                parent = candidates[0]
                # A varying profile cannot supply a constant whole-road grade.
                if 'grade' not in parent:
                    replacements.update({r['id']: parent['id'] for r in strips})
                else:
                    issues.append('Containing roadway has a grade; preserve pending profile review')
            else:
                issues.append('No unique containing physical roadway for grade strips')
    # Exact duplicates are equivalent only when all semantic fields also match.
    seen = {}
    for r in regions:
        if r['id'] in replacements or r.get('kind') not in ('roadway', 'one_way_roadway'):
            continue
        data = dict(r); data.pop('id')
        data['boundary'] = boundary_key(data.get('boundary', []))
        key = json.dumps(data, sort_keys=True)
        if identities is not None:
            key+=json.dumps(identities.get(r['id'],['unknown',r['id']]),sort_keys=True)
        if key in seen:
            replacements[r['id']] = seen[key]
        else:
            seen[key] = r['id']
    proven={}
    if identities:
        for r in regions:
            if r['id'] in replacements or r['id'] not in identities:continue
            key=(r['kind'],boundary_key(r.get('boundary',[])),json.dumps(identities[r['id']],sort_keys=True))
            if key not in proven:proven[key]=r;continue
            prior=proven[key];merged=compatible_properties(prior,r)
            if merged is None:
                issues.append('Same-source coincident roadway has conflicting observations; retained separately')
            else:
                replacements[r['id']]=prior['id'];property_merges.append(r['id']);proven[key]=merged
    result = apply_replacements(scene, replacements, property_merges) if replacements else scene
    return result, {'removed': len(replacements), 'replacements': replacements,
                    'property_merges':property_merges,
                    'issues': issues,
                    'grade_note': ('Varying measured profile retained in archived trace; '
                                   'no whole-road constant invented') if strips else None}


def apply_replacements(scene, replacements, property_merges=()):
    from .compatibility import remap_regions
    # Avoid copying the retired 300 structures and their observation masks.
    base = dict(scene)
    base['structures'] = [r for r in scene.get('structures', []) if r['id'] not in replacements]
    if property_merges:
        by_id={r['id']:r for r in scene['structures']}
        updates={}
        for ident in property_merges:
            target=replacements[ident]
            while target in replacements:target=replacements[target]
            value=compatible_properties(updates.get(target,by_id[target]),by_id[ident])
            if value is None:raise ValueError('Roadway properties conflict in a later frame')
            updates[target]=value
        base['structures']=[updates.get(r['id'],r) for r in base['structures']]
    return remap_regions(base, replacements)


def merge_highways(path, regions, polygons, source_roads, way_groups=()):
    """Group ways by verified continuation or bound divided-road identity.

    Turning connectors do not merge two roads. A disconnected or holed surface
    retains its proven way identity with the unrepresentable boundary omitted.
    """
    import math
    import xml.etree.ElementTree as ET
    from shapely.ops import unary_union
    from .geometry import reference
    roads={int(r.attrib['id']):r for r in ET.parse(path).getroot().findall('road')}
    highway_by_road={}
    for r in regions:
        if r['kind']=='highway':
            for road in source_roads.get(r['id'],[]):highway_by_road.setdefault(road,[]).append(r['id'])
    parent={i:i for i in highway_by_road}
    def root(i):
        while parent[i]!=i:i=parent[i]
        return i
    def join(ids):
        if not all(i in parent for i in ids):return
        for i in ids:parent[root(i)]=root(ids[0])
    for ident,road in roads.items():
        if ident not in parent:continue
        geoms=road.findall('./planView/geometry')
        if not geoms:continue
        adjacent=[]
        for side in ('predecessor','successor'):
            link=road.find('./link/'+side)
            if link is not None and link.get('elementType')=='road' and int(link.get('elementId')) in parent:
                adjacent.append(int(link.get('elementId')))
        named=[other for other in adjacent if road.get('name') and road.get('name')==roads[other].get('name')]
        if named:join([ident,*named])
        if len(adjacent)==2 and roads[adjacent[0]].get('name') and roads[adjacent[0]].get('name')==roads[adjacent[1]].get('name'):
            join([ident,*adjacent])
        if any(g.find('line') is None for g in geoms):continue
        endpoints=[]
        for side,station in [('predecessor',0.),('successor',float(road.attrib['length']))]:
            link=road.find('./link/'+side)
            if link is None or link.get('elementType')!='road':continue
            other_id=int(link.get('elementId'))
            if other_id not in parent:continue
            other=roads[other_id];other_geoms=other.findall('./planView/geometry')
            at=0. if link.get('contactPoint')=='start' else float(other.attrib['length'])
            g=next(g for g in reversed(geoms) if float(g.attrib['s'])<=station+1e-9)
            og=next(g for g in reversed(other_geoms) if float(g.attrib['s'])<=at+1e-9)
            x,y,h,_=reference(g,station);ox,oy,oh,_=reference(og,at)
            # Same tangent line and coincident native endpoints verify a straight
            # continuation even when generated segment names differ.
            if math.hypot(x-ox,y-oy)<=1e-5 and abs(math.sin(h-oh))<=1e-8:
                endpoints.append(other_id)
        if endpoints:join([ident,*endpoints])
    for group in way_groups:join(group['roads'])
    groups={}
    for road in parent:groups.setdefault(root(road),[]).append(road)
    by_id={r['id']:r for r in regions};replacements={};issues=[]
    for members in groups.values():
        ids=sorted({i for road in members for i in highway_by_road[road]})
        if len(ids)<2:continue
        # Native trigonometry may separate a mathematically shared edge by a
        # few ulps. Snap at 10 nanometres only after topology proved continuation;
        # this is finer than the original float32 capture and trace coordinates.
        from shapely import set_precision
        shape=unary_union([set_precision(polygons[i],1e-8) for i in ids if i in polygons]) if all(i in polygons for i in ids) else None
        # A verified divided-road design names its two carriageways as one
        # way. Its dividing section lies between measured, coextensive outer
        # edges; this is not a hull applied to arbitrary neighbouring roads.
        for group in way_groups:
            if not set(group['roads'])<=set(members)or not group.get('include_dividing_section'):continue
            primary=group['parallel_carriageways'];corridors=[];ranges=[]
            h=float(roads[primary[0]].find('./planView/geometry').get('hdg'));axis=(math.cos(h),math.sin(h))
            valid=shape is not None
            for road in primary:
                geoms=roads[road].findall('./planView/geometry')
                valid=valid and all(g.find('line')is not None and abs(math.sin(float(g.get('hdg'))-h))<1e-8 for g in geoms)
                pieces=[polygons[i]for i in highway_by_road[road]if i in polygons]
                surface=unary_union(pieces);corridors.append(surface)
                if surface.geom_type!='Polygon':valid=False;continue
                coords=list(surface.exterior.coords);ts=[x*axis[0]+y*axis[1]for x,y in coords];us=[-x*axis[1]+y*axis[0]for x,y in coords]
                ranges.append((min(ts),max(ts)))
                valid=valid and abs(surface.area-(max(ts)-min(ts))*(max(us)-min(us)))<=1e-5
            valid=valid and len(ranges)==len(primary)and all(max(abs(a-b)for a,b in zip(span,ranges[0]))<=1e-5 for span in ranges)
            envelope=unary_union(corridors).convex_hull
            valid=valid and all(envelope.buffer(1e-6).covers(polygons[i])for road in group['roads']for i in highway_by_road[road]if i in polygons)
            if valid:shape=unary_union([shape,envelope])
            else:shape=None
        keep=ids[0]
        if shape is not None and shape.geom_type=='Polygon' and not shape.interiors:
            by_id[keep]['boundary']=[list(v) for v in shape.exterior.coords[:-1]]
        else:
            issues.append('Highway continuation '+str(sorted(members))+' has no single simple Core boundary; verified way identity is retained; occupancy uses the source surface only where established')
            by_id[keep].pop('boundary',None)
        if shape is not None:polygons[keep]=shape
        else:polygons.pop(keep,None)
        source_roads[keep]=sorted(members)
        for ident in ids[1:]:replacements[ident]=keep;polygons.pop(ident,None)
    if replacements:regions[:]=[r for r in regions if r['id'] not in replacements]
    return replacements,issues
