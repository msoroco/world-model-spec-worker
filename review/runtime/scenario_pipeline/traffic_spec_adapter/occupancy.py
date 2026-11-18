"""Complete producer occupancy, preserving unchanged Core unknown semantics."""
from shapely.geometry import Polygon

def recompute(scene, footprints, *, source_ids, surfaces=None, unresolved_grade=(), unresolved_vertical=()):
    """Compare source-bound bodies with every FINAL exported structure.

    Footprints/surface unions and identities are verified by the caller. Touching
    boundaries count as overlap, matching the existing polygon intersection rule.
    Partial supported pairs remain evidence; Core queries stay unknown per track.
    """
    structures=scene.get('structures',[])
    ids=[s['id'] for s in structures]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate final occupancy structure identity')
    tracks=[u['track'] for u in scene.get('users',[])]
    if len(tracks)!=len(set(tracks)):raise ValueError('Duplicate occupancy track identity')
    if any(t not in tracks for t in scene.get('occupancy_observed',[])):
        raise ValueError('Unknown occupancy_observed track reference')
    if any(t not in tracks or r not in ids for t,r in scene.get('occupies',[])):
        raise ValueError('Unknown occupancy track/structure reference')
    surfaces=surfaces or {}; shapes={}; gaps={}; ambiguous=set(unresolved_grade)
    coincident={}
    for s in structures:
        rid=s['id'];reasons=[]
        if rid not in source_ids:reasons.append('unverified_structure_identity')
        # Final exported polygon wins, including its declared invalidity.
        # A verified union substitutes only for an absent exported polygon.
        if s.get('boundary') is not None:
            try:shape=Polygon(s['boundary'])
            except (TypeError,ValueError):shape=None
        else:shape=surfaces.get(rid)
        if shape is None or shape.is_empty or not shape.is_valid or shape.area<=0:
            reasons.append('missing_or_invalid_region_geometry')
        else:
            shapes[rid]=shape
            if s['kind'] in ('roadway','one_way_roadway'):
                key=shape.normalize().wkb
                if key in coincident:ambiguous.update((rid,coincident[key]))
                else:coincident[key]=rid
        if reasons:gaps[rid]=reasons
    vertical=set(unresolved_vertical)
    old={(t,r) for t,r in scene.get('occupies',[])};old_observed=set(scene.get('occupancy_observed',[]));pairs=[];observed=[];coverage=[]
    for track in tracks:
        body=footprints.get(track);missing={k:list(v) for k,v in gaps.items()};compared=0
        valid=body is not None and not body.is_empty and body.is_valid and body.area>0
        if valid:
            for rid,shape in shapes.items():
                if rid in gaps:continue
                overlap=body.intersects(shape)
                if overlap and (rid in ambiguous or (track,rid)in vertical):
                    missing.setdefault(rid,[]).append('unresolved_grade_separation');continue
                compared+=1
                if overlap:pairs.append([track,rid])
            if not missing:observed.append(track)
        coverage.append({'track':track,'structures':len(structures),'compared':compared,
                         'complete':valid and not missing,'footprint_source_available':valid,
                         'footprint_gap':None if valid else 'missing_or_invalid_source_bound_footprint',
                         'unresolved':missing})
    scene['occupies']=sorted(pairs);scene['occupancy_observed']=sorted(observed)
    current={tuple(p) for p in pairs}
    return {'changed':old!=current or old_observed!=set(observed),'tracks':coverage,'complete_tracks':len(observed),'incomplete_tracks':len(tracks)-len(observed),
            'removed_unsupported_pairs':sorted(old-current),'added_supported_pairs':sorted(current-old)}


def unresolved_obstruction_heights(scene, vertices_by_track, fields):
    """Scope 2D obstruction overlap to measured same-frame original body Z."""
    import math
    unresolved=set()
    sources={i:v['_obstruction_geometry_source']for i,v in fields.items()if v.get('_obstruction_geometry_source')}
    for user in scene.get('users',[]):
        track=user['track'];vertices=vertices_by_track.get(track)
        valid=(isinstance(vertices,list)and len(vertices)==8 and all(isinstance(p,list)and len(p)==3
            and all(type(x)in(int,float)and math.isfinite(x)for x in p)for p in vertices))
        for ident,source in sources.items():
            plane=source.get('native_plane_height_m');interval=source['vertical_range_m']
            if not valid or plane is None:
                unresolved.add((track,ident));continue
            bottom=min(p[2]for p in vertices);top=max(p[2]for p in vertices)
            if not (bottom<=plane<=top and bottom<=interval[1]and interval[0]<=top):
                unresolved.add((track,ident))
    return unresolved


def native_single_plane(path, *, lane_kinds=None):
    """Prove one native elevation plane from explicit complete source records.

    No absent elevation defaults, coordinate fitting, rendered-surface estimate,
    or tolerance is introduced. Nonconstant/multilevel maps need further original
    height-scope evidence; their potentially overlapping comparisons stay unknown.
    """
    import math
    import xml.etree.ElementTree as ET
    if path is None:return False
    try:
        roads=ET.parse(path).getroot().findall('road')
        if not roads:return False
        height=None
        for road in roads:
            for modifier in road.findall('./lateralProfile/*'):
                if any(float(modifier.get(k,'0'))!=0 for k in ('a','b','c','d')):return False
            for lane in road.findall('./lanes/laneSection/*/lane'):
                if lane_kinds is not None and lane.get('type') not in lane_kinds:continue
                for value in lane.findall('height'):
                    heights=[float(value.get(k,'0'))for k in ('inner','outer')]
                    if any(not math.isfinite(v)or v!=0 for v in heights):return False
            records=road.findall('./elevationProfile/elevation')
            if not records or float(records[0].get('s'))!=0:return False
            starts=[float(e.get('s')) for e in records]
            length=float(road.get('length'))
            if any(not math.isfinite(v) for v in starts+[length]) or any(a>=b for a,b in zip(starts,starts[1:])) or starts[-1]>length:return False
            for record in records:
                values=[float(record.get(k)) for k in ('a','b','c','d')]
                if any(not math.isfinite(v) for v in values) or any(values[i]!=0 for i in (1,2,3)):return False
                if height is None:height=values[0]
                elif values[0]!=height:return False
        return True
    except (OSError,ValueError,TypeError,ET.ParseError):return False


def native_driving_surface(path):
    """Exact native Driving surface on one explicit source plane, or unknown.

    The global proof remains unchanged. Non-driving heights are not certified,
    and no source polygon is rounded, buffered, fitted, or enlarged here.
    """
    if not native_single_plane(path,lane_kinds={'driving'}):return None
    from .geometry import static_map
    from shapely.ops import unary_union
    try:
        regions,_,_=static_map(path,partial=True)
        shapes=[Polygon(r['boundary'])for r in regions if r['kind']=='lane'and r.get('boundary')]
        if not shapes or any(not p.is_valid or p.is_empty or p.area<=0 for p in shapes):return None
        return unary_union(shapes)
    except (OSError,ValueError,TypeError):return None


def unresolved_surface_heights(scene,footprints,source_ids,surface,*,surfaces=None):
    """Only exact body/surface overlap on native Driving plane is certified.

    Source identity is a separate prerequisite. Raised sidewalks/props and any
    overlap outside the known travel surface remain unknown per track/region.
    """
    surfaces=surfaces or {};unresolved=set()
    eligible={'lane','roadway','one_way_roadway','highway','intersection','crosswalk','stop_line','centre_line'}
    for user in scene.get('users',[]):
        track=user['track'];body=footprints.get(track)
        if body is None or body.is_empty or not body.is_valid:continue
        for region in scene.get('structures',[]):
            rid=region['id']
            if rid not in source_ids:continue
            try:shape=Polygon(region['boundary'])if region.get('boundary')is not None else surfaces.get(rid)
            except (TypeError,ValueError):continue
            if shape is None or not shape.is_valid or shape.is_empty:continue
            overlap=body.intersection(shape)
            if overlap.is_empty:continue
            if surface is None or region['kind']not in eligible or not surface.covers(overlap):unresolved.add((track,rid))
    return unresolved
