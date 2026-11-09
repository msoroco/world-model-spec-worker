"""Observed body geometry and sampled OpenDRIVE regions, in TrafficSpec's frame.

Lane IDs identify full (road, section, lane) regions. Compatible consecutive
road segments share one roadway; property producers cannot add overlays.
Sampling is geometric approximation, never a legal interpretation. OpenDRIVE
is already right-handed; only CARLA observations need y/yaw reflection.
"""
import math
import hashlib
from pathlib import Path

# Freeze the implementation identity used by this process; an unrelated edit
# during a long batch must not label old executable code with new file hashes.
_SOURCE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_ROADWAYS_SHA=hashlib.sha256(Path(__file__).with_name("roadways.py").read_bytes()).hexdigest()

import warnings
import xml.etree.ElementTree as ET


def xy(v):
    return [float(v[0]), -float(v[1])]


def body(vertices, heading):
    """Return world-frame body centre, half sizes and its exact recorded footprint."""
    from shapely.geometry import MultiPoint
    h = math.radians(heading)
    f, r = (math.cos(h), math.sin(h)), (-math.sin(h), math.cos(h))
    longitudinal = [p[0]*f[0]+p[1]*f[1] for p in vertices]
    lateral = [p[0]*r[0]+p[1]*r[1] for p in vertices]
    centre = [sum(p[i] for p in vertices)/len(vertices) for i in range(3)]
    extent = [(max(longitudinal)-min(longitudinal))/2,
              (max(lateral)-min(lateral))/2,
              (max(p[2] for p in vertices)-min(p[2] for p in vertices))/2]
    return xy(centre), extent, MultiPoint([xy(p) for p in vertices]).convex_hull


def polynomial(nodes, station, offset_name='s'):
    eligible = [n for n in nodes if float(n.attrib[offset_name]) <= station+1e-9]
    if not eligible:
        return 0.
    n = eligible[-1]; d = station-float(n.attrib[offset_name])
    return sum(float(n.attrib.get(k, 0))*d**i for i,k in enumerate('abcd'))


def reference(g, station):
    d = station-float(g.attrib['s']); h = float(g.attrib['hdg'])
    x,y = float(g.attrib['x']),float(g.attrib['y'])
    if g.find('line') is not None:
        return x+d*math.cos(h),y+d*math.sin(h),h,0.
    arc = g.find('arc')
    if arc is not None:
        k = float(arc.attrib['curvature'])
        if abs(k)<1e-12:
            return x+d*math.cos(h),y+d*math.sin(h),h,0.
        return x+(math.sin(h+k*d)-math.sin(h))/k,y-(math.cos(h+k*d)-math.cos(h))/k,h+k*d,k
    raise ValueError('Unsupported OpenDRIVE geometry: retain source; do not invent boundary')


def clean_boundary(points):
    """Collapse numerically coincident samples, including zero-radius arc edges."""
    result=[]
    for point in points:
        if not result or math.dist(result[-1],point)>1e-9:result.append(point)
    if len(result)>1 and math.dist(result[0],result[-1])<=1e-9:result.pop()
    return result


def lane_marking(source_lane, *, complete=False):
    """Map explicit paint, or verified no paint in a complete generated map.

    ``other`` is the non-white/yellow colour tag for an absent painted line;
    it is never substituted for an unavailable colour on an existing line.
    """
    marks=source_lane.findall('roadMark') if source_lane is not None else []
    if not marks:return ['none','other'] if complete else None
    values={(m.get('type'),m.get('color')) for m in marks}
    kinds={'broken':'broken','solid':'solid','solid solid':'double_solid',
           'solid broken':'solid_broken','broken solid':'solid_broken',
           'botts dots':'dotted','curb':'curb','none':'none'}
    if len(values)!=1 or float(marks[0].get('sOffset',0))!=0:return None
    typ,color=next(iter(values))
    if typ not in kinds:return None
    if color in ('white','yellow'):return [kinds[typ],color]
    if typ=='none' or color in ('blue','green','red','orange','other','none'):
        return [kinds[typ],'other']
    return None


def _static_map(path, junctions=False, junction_report=None, native_junction_boxes=(), include_non_driving=False, public_way_roads=(), partial=False, source_roads=None, source_regions=None, complete_map=False):
    """Build all source-map lanes and local roadway patches from line/arc geometry.

    Width/offset polynomials are evaluated at samples. Maximum sample spacing is
    2 m; polygons and occupancy are estimates. Unsupported geometry is an error,
    not an empty map. Variable lane direction/width/markings remain unasserted.
    """
    from shapely.geometry import Polygon
    regions, polygons, keys = [], {}, {}
    endpoints={}
    source = ET.parse(path).getroot()
    if any(type(ident)is not int for ident in public_way_roads):raise ValueError('Public-way road references must be native integer IDs')
    if set(public_way_roads)-{int(road.get('id'))for road in source.findall('road')}:raise ValueError('Declared public-way road ID absent from realized native map')
    for road in sorted(source.findall('road'), key=lambda r:int(r.attrib['id'])):
        first_region = len(regions)
        rid=int(road.attrib['id']); length=float(road.attrib['length'])
        geoms=road.findall('./planView/geometry')
        sections=road.findall('./lanes/laneSection')
        for section_index, section in enumerate(sections):
            start=float(section.attrib['s'])
            end=float(sections[section_index+1].attrib['s']) if section_index+1<len(sections) else length
            lanes=sorted(section.findall('./left/lane')+section.findall('./right/lane'),key=lambda l:int(l.attrib['id']))
            driving=[l for l in lanes if l.attrib.get('type')=='driving']
            def edge(station, lane_id, outer):
                g=next(g for g in reversed(geoms) if float(g.attrib['s'])<=station+1e-9)
                x,y,h,_=reference(g,station)
                offset=polynomial(road.findall('./lanes/laneOffset'),station)
                sign=1 if lane_id>0 else -1
                for l in sorted((l for l in lanes if int(l.attrib['id'])*sign>0),key=lambda l:abs(int(l.attrib['id']))):
                    lid=int(l.attrib['id'])
                    if abs(lid)<abs(lane_id) or (lid==lane_id and outer):
                        offset+=sign*polynomial(l.findall('width'),station-start,'sOffset')
                return [x-math.sin(h)*offset,y+math.cos(h)*offset]
            stations=sorted(set([start,end]+[start+i*2 for i in range(1,math.ceil((end-start)/2))]+[float(g.attrib['s']) for g in geoms if start<float(g.attrib['s'])<end]))
            if rid in public_way_roads:
                # Public status is an explicit map assumption. The measured
                # envelope includes every native surface, not only roadway.
                nonzero=[int(l.attrib['id']) for l in lanes if l.findall('width')]
                pos=[lid for lid in nonzero if lid>0];neg=[lid for lid in nonzero if lid<0]
                if pos or neg:
                    left=max(pos) if pos else min(neg,key=abs)
                    right=min(neg) if neg else min(pos,key=abs)
                    boundary=[edge(st,left,bool(pos)) for st in stations]+[edge(st,right,bool(neg)) for st in reversed(stations)]
                    boundary=clean_boundary(boundary)
                    polygon=Polygon(boundary)
                    if not polygon.is_valid or polygon.area<=0:
                        # Union measured station strips instead of forcing a
                        # self-intersecting perimeter into a Core polygon.
                        from shapely.ops import unary_union
                        strips=[]; measured=True
                        for a,b in zip(stations,stations[1:]):
                            quad=Polygon([edge(a,left,bool(pos)),edge(b,left,bool(pos)),edge(b,right,bool(neg)),edge(a,right,bool(neg))])
                            if quad.is_valid and quad.area>1e-12:strips.append(quad)
                            elif quad.convex_hull.area>1e-12:
                                # Crossing measured edges do not determine a
                                # surface. Choosing a diagonal would invent it.
                                measured=False;break
                        polygon=unary_union(strips) if measured else Polygon()
                    ident=len(regions)+1;region={'id':ident,'kind':'highway'}
                    if polygon.geom_type=='Polygon' and not polygon.interiors and polygon.area>0:
                        region['boundary']=[list(p) for p in polygon.exterior.coords[:-1]]
                    elif junction_report is not None:
                        junction_report.append({'unknown_geometry':'Public road '+str(rid)+' has no single simple Core boundary; occupancy uses the source surface only where established'})
                    regions.append(region)
                    if not polygon.is_empty:polygons[ident]=polygon
            for lane in driving:
                lid=int(lane.attrib['id']); ident=len(regions)+1
                boundary=[edge(s,lid,False) for s in stations]+[edge(s,lid,True) for s in reversed(stations)]
                boundary=clean_boundary(boundary)
                polygon=Polygon(boundary)
                if not polygon.is_valid or polygon.area <= 1e-8:
                    issue = 'Unrepresentable native lane boundary '+str((rid,section_index,lid))
                    if not partial: raise ValueError(issue)
                    if junction_report is not None: junction_report.append({'unknown_geometry':issue})
                    continue
                same=sorted([int(l.attrib['id']) for l in driving if int(l.attrib['id'])*lid>0],key=abs)
                info={'ordinal':same.index(lid)+1,'count':len(same)}
                widths=lane.findall('width')
                if widths and float(widths[0].attrib.get('sOffset',0))==0 and all(
                        all(float(w.attrib.get(k,0))==0 for k in 'bcd') and float(w.attrib['a'])==float(widths[0].attrib['a']) for w in widths):
                    info['width']=float(widths[0].attrib['a'])
                inner=next((l for l in lanes if int(l.attrib['id'])==lid-(1 if lid>0 else -1)),None)
                if abs(lid)==1:inner=section.find('./center/lane')
                for side,source_lane in [('left',inner),('right',lane)]:
                    value=lane_marking(source_lane,complete=complete_map)
                    if value is not None:info['marking_'+side]=value
                # A winding lane has no single direction vector. Do not freeze
                # direction at the ego station and give it to all other actors.
                headings=[reference(next(g for g in reversed(geoms) if float(g.attrib['s'])<=s+1e-9),s)[2] for s in stations]
                if max(headings)-min(headings)<1e-8:
                    h=headings[0]+(math.pi if lid>0 else 0)
                    info['direction']=[math.cos(h),math.sin(h)]
                regions.append({'id':ident,'kind':'lane','boundary':boundary,'lane':info})
                polygons[ident]=polygon; keys[(rid,section_index,lid)]=ident
                endpoints[(rid,section_index,lid)]=[[edge(s,lid,False),edge(s,lid,True)] for s in (start,end)]
                if source_regions is not None:
                    source_regions[ident]={'road_id':rid,'section':section_index,'lane_id':lid,
                        'samples':[[s,edge(s,lid,False),edge(s,lid,True)] for s in stations]}
            if include_non_driving:
                # Native lane type is geometry provenance, not a legal district
                # or an invented sidewalk/shoulder inferred from a blank area.
                for lane in lanes:
                    kind={'sidewalk':'sidewalk','shoulder':'shoulder','biking':'bicycle_lane_or_path',
                          'median':'median_or_divider'}.get(lane.attrib.get('type'))
                    if not kind:continue
                    lid=int(lane.attrib['id'])
                    boundary=[edge(st,lid,False) for st in stations]+[edge(st,lid,True) for st in reversed(stations)]
                    boundary=clean_boundary(boundary)
                    polygon=Polygon(boundary)
                    if polygon.area<=1e-8:continue
                    if not polygon.is_valid:
                        # A sidewalk/shoulder offset around a tight corner can fold over itself; that region is
                        # left out (recorded) rather than repaired into geometry the source does not state.
                        import hashlib
                        from pathlib import Path
                        identity=hashlib.sha256(Path(path).read_bytes()).hexdigest()+':'+str((rid,section_index,lid,kind))
                        ident=10**12+int.from_bytes(hashlib.sha256(identity.encode()).digest()[:6],'big')
                        regions.append({'id':ident,'kind':kind})
                        if junction_report is not None:junction_report.append({'unknown_geometry':'Native '+kind+' '+str((rid,section_index,lid))+' enumerated with unknown boundary; no polygon repair or point-extent substitution'})
                        continue
                    ident=len(regions)+1
                    regions.append({'id':ident,'kind':kind,'boundary':boundary})
                    polygons[ident]=polygon
                    if source_regions is not None:source_regions[ident]={'road_id':rid,'section':section_index,'lane_id':lid,
                        'samples':[[st,edge(st,lid,False),edge(st,lid,True)]for st in stations]}
            from .roadways import roadway_intervals
            for a,b,properties in roadway_intervals(road,geoms,start,end):
                if not driving:continue
                pos=[int(l.attrib['id']) for l in driving if int(l.attrib['id'])>0]
                neg=[int(l.attrib['id']) for l in driving if int(l.attrib['id'])<0]
                sample=[a+i*(b-a)/max(1,math.ceil((b-a)/2)) for i in range(max(1,math.ceil((b-a)/2))+1)]
                left=max(pos) if pos else min(neg,key=abs); right=min(neg) if neg else min(pos,key=abs)
                boundary=[edge(s,left,bool(pos)) for s in sample]+[edge(s,right,bool(neg)) for s in reversed(sample)]
                boundary=clean_boundary(boundary)
                ident=len(regions)+1; p=Polygon(boundary)
                if p.area<=1e-8:continue   # degenerate patch from a very short geometry record, as for non-driving lanes
                if not p.is_valid:
                    if not partial:raise ValueError('Invalid roadway patch')
                    if junction_report is not None:junction_report.append({'unknown_geometry':'Invalid roadway patch, road '+str(rid)})
                    continue
                region=dict(id=ident,kind='roadway',boundary=boundary,**properties)
                regions.append(region);polygons[ident]=p
                segment_samples=[]
                for geometry in geoms:
                    low=max(a,float(geometry.attrib['s']));high=min(b,float(geometry.attrib['s'])+float(geometry.attrib['length']))
                    if high<=low:continue
                    count=max(1,math.ceil((high-low)/2));stations_for_segment=[low+i*(high-low)/count for i in range(count+1)]
                    segment_samples.append([[st,edge(st,left,bool(pos)),edge(st,right,bool(neg))]for st in stations_for_segment])
                if source_regions is not None:
                    elevations=road.findall('./elevationProfile/elevation')
                    cuts=sorted({a,b,*[float(e.get('s')) for e in elevations if a<float(e.get('s'))<b]})
                    profile=[]
                    for low,high in zip(cuts,cuts[1:]):
                        active=[e for e in elevations if float(e.get('s'))<=low+1e-9]
                        if active:profile.append(dict(active[-1].attrib,interval=[low,high]))
                    flat=None
                    if profile and all(all(abs(float(e.get(k,0)))<=1e-12 for k in 'bcd') for e in profile):
                        heights=[float(e.get('a',0)) for e in profile]
                        if max(heights)-min(heights)<=1e-9:flat=heights[0]
                    source_regions[ident]={'road_id':rid,'section':section_index,'interval':[a,b],
                        'samples':[[st,edge(st,left,bool(pos)),edge(st,right,bool(neg))]for st in sample],
                        'segments':segment_samples,
                        'lane_ids':sorted(int(l.get('id')) for l in driving),'junction':int(road.get('junction','-1')),
                        'elevation_profile':profile,'flat_z':flat}
        if source_roads is not None:
            source_roads.update({r['id']: [rid] for r in regions[first_region:]})
    # Neighbours mean same-direction lanes only. Opposing lanes are not left/right neighbours.
    for key,ident in keys.items():
        rid,section,lid=key; info=next(r['lane'] for r in regions if r['id']==ident)
        sign=1 if lid>0 else -1
        if (rid,section,lid-sign) in keys: info['left']=keys[(rid,section,lid-sign)]
        if (rid,section,lid+sign) in keys: info['right']=keys[(rid,section,lid+sign)]
    by_id={r['id']:r for r in regions}
    roads={int(r.attrib['id']):r for r in source.findall('road')}
    for (rid,section,lid),ident in keys.items():
        road=roads[rid];sections=road.findall('./lanes/laneSection')
        lane=next(l for l in sections[section].findall('./left/lane')+sections[section].findall('./right/lane') if int(l.attrib['id'])==lid)
        forward='successor' if lid<0 else 'predecessor'
        link=lane.find('./link/'+forward)
        target_section=section+(1 if lid<0 else -1);target_road=rid
        target_lane=int(link.get('id')) if link is not None else lid
        if link is None and not complete_map:continue
        if not 0<=target_section<len(sections):
            road_link=road.find('./link/'+forward)
            if road_link is None:
                if complete_map:by_id[ident]['lane']['leads_to']=[]
                continue
            if road_link.get('elementType')!='road':continue
            target_road=int(road_link.get('elementId'))
            if target_road not in roads:continue
            target_section=0 if road_link.get('contactPoint')=='start' else len(roads[target_road].findall('./lanes/laneSection'))-1
        target=keys.get((target_road,target_section,target_lane))
        if target is not None:
            if link is None:
                # Missing lane links are recoverable only for a unique native
                # road/section continuation with the same strip and shared end.
                # A nearby lane or a merely overlapping footprint is insufficient.
                from shapely.geometry import LineString
                source_end=endpoints[(rid,section,lid)][1 if lid<0 else 0]
                target_end=endpoints[(target_road,target_section,target_lane)][0 if target_lane<0 else 1]
                if min(math.dist(*source_end),math.dist(*target_end))<=1e-9:continue
                distance=LineString(source_end).hausdorff_distance(LineString(target_end))
                if not math.isfinite(distance) or distance>1e-5:continue
            by_id[ident]['lane']['leads_to']=[target]
    if junctions:
        from shapely.ops import unary_union
        roads={int(r.attrib['id']):r for r in source.findall('road')}
        junction_ids={int(r.attrib['junction']) for r in roads.values() if int(r.attrib.get('junction','-1'))>=0}
        junction_regions={}
        boxes={j['id']:j for j in native_junction_boxes}
        for jid in sorted(junction_ids):
            members=[polygons[ident] for (rid,_,_),ident in keys.items()
                     if int(roads[rid].attrib.get('junction','-1'))==jid]
            union=unary_union(members)
            if jid in boxes:
                from shapely.geometry import MultiPoint
                union=MultiPoint([xy(p) for p in boxes[jid]['body_vertices_m']]).convex_hull
            components=list(union.geoms) if union.geom_type=='MultiPolygon' else [union]
            emitted=[]
            for component in components:
                # Core boundaries cannot encode holes. Preserve ambiguity rather
                # than fill islands or take a bounding box/convex hull.
                if component.geom_type!='Polygon' or component.interiors:continue
                ident=len(regions)+1
                regions.append({'id':ident,'kind':'intersection',
                                'boundary':[list(p) for p in component.exterior.coords[:-1]]})
                polygons[ident]=component;emitted.append(ident)
            junction_regions[jid]=emitted
            if source_roads is not None:
                meeting={int(c.attrib['incomingRoad']) for j in source.findall('junction') if int(j.attrib['id'])==jid for c in j.findall('connection')}
                source_roads.update({i: sorted(meeting) for i in emitted})
            if junction_report is not None:
                junction_report.append({'opendrive_junction_id':jid,'region_ids':emitted,
                    'method':'Recorded native CARLA Junction.bounding_box, a coarse map extent' if jid in boxes else 'Union of sampled native junction driving-lane polygons; disconnected parts kept separate, holes omitted',
                    'scope':'Estimated physical connector surface; not a painted stop line or a legal boundary determination'})
        by_id={r['id']:r for r in regions}
        for junction in source.findall('junction'):
            jid=int(junction.attrib['id'])
            for connection in junction.findall('connection'):
                incoming=int(connection.attrib['incomingRoad']);connecting=int(connection.attrib['connectingRoad'])
                if incoming not in roads or connecting not in roads:continue
                incoming_sections=roads[incoming].findall('./lanes/laneSection')
                target_sections=roads[connecting].findall('./lanes/laneSection')
                target_section=0 if connection.attrib.get('contactPoint')=='start' else len(target_sections)-1
                for link in connection.findall('laneLink'):
                    origin=int(link.attrib['from']);target=int(link.attrib['to'])
                    key=(incoming,len(incoming_sections)-1 if origin<0 else 0,origin)
                    target_id=keys.get((connecting,target_section,target))
                    if key not in keys or target_id is None:continue
                    lane=by_id[keys[key]]['lane']
                    lane['leads_to']=sorted(set(lane.get('leads_to',[])+[target_id]))
                    # A scalar Core reference cannot represent several disconnected
                    # intersection components. Only attach an unambiguous region.
                    matches=[i for i in junction_regions.get(jid,[]) if polygons[i].intersects(polygons[target_id])]
                    if len(matches)==1:
                        lane['enters_intersection']=matches[0]
    return regions,polygons,keys


def native_centre_lines(path):
    """Source-map dividers between opposing driving lanes, as directed polylines.

    The reference direction is OpenDRIVE increasing s. Lane offsets are retained.
    A one-way road has no opposing-direction divider. Paint attributes remain
    source evidence; the polyline never invents a painted width or legal zone.
    """
    from shapely.geometry import LineString
    observations=[]
    for road in ET.parse(path).getroot().findall('road'):
        sections=road.findall('./lanes/laneSection');geoms=road.findall('./planView/geometry')
        for index,section in enumerate(sections):
            if not section.findall("./left/lane[@type='driving']") or not section.findall("./right/lane[@type='driving']"):
                continue
            start=float(section.attrib['s'])
            end=float(sections[index+1].attrib['s']) if index+1<len(sections) else float(road.attrib['length'])
            count=max(1,math.ceil((end-start)/2))
            stations=sorted(set([start+i*(end-start)/count for i in range(count+1)]+[float(g.attrib['s'])for g in geoms if start<float(g.attrib['s'])<end]))
            boundary=[]
            for station in stations:
                g=next(g for g in reversed(geoms)if float(g.attrib['s'])<=station+1e-9)
                x,y,h,_=reference(g,station)
                offset=polynomial(road.findall('./lanes/laneOffset'),station)
                boundary.append([x-math.sin(h)*offset,y+math.cos(h)*offset])
            observations.append({'region':{'kind':'centre_line','boundary':boundary},'shape':LineString(boundary),
                'source':{'road_id':int(road.attrib['id']),'section_id':index,'method':'Native opposing driving-lane divider; directed increasing source s; <=2m sampling',
                          'centre_road_marks':[dict(mark.attrib)for mark in section.findall('./center/lane/roadMark')],
                          'scope':'Geometric divider; paint visibility and legal interpretation are not inferred'}})
    return observations


def painted_map_objects(path):
    """Native OpenDRIVE StopLine/crosswalk objects, with no invented paint width.

    Zero-width StopLine objects remain line segments. Polygon-dependent queries
    may be unknown; supplementary geometry retains that representation explicitly.
    """
    from shapely.geometry import Polygon, LineString
    observations=[]
    for road in ET.parse(path).getroot().findall('road'):
        geoms=road.findall('./planView/geometry')
        for obj in road.findall('./objects/object'):
            kind='stop_line' if obj.attrib.get('name')=='StopLine' else 'crosswalk' if obj.attrib.get('type')=='crosswalk' else None
            if kind is None:continue
            station=float(obj.attrib['s']);offset=float(obj.attrib['t'])
            geometry=next(g for g in reversed(geoms) if float(g.attrib['s'])<=station+1e-9)
            x,y,heading,_=reference(geometry,station)
            x-=math.sin(heading)*offset;y+=math.cos(heading)*offset
            heading+=float(obj.attrib.get('hdg',0))
            corners=obj.findall('./outline/cornerLocal')+obj.findall('./outlines/outline/cornerLocal')
            if corners:
                local=[(float(c.attrib['u']),float(c.attrib['v'])) for c in corners]
            else:
                length=float(obj.attrib.get('length',0));width=float(obj.attrib.get('width',0))
                if length<=0:continue
                local=[(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)] if width>1e-8 else [(-length/2,0),(length/2,0)]
            boundary=[[x+u*math.cos(heading)-v*math.sin(heading),y+u*math.sin(heading)+v*math.cos(heading)] for u,v in local]
            polygonal=kind!='stop_line' or float(obj.attrib.get('width',0))>1e-8
            shape=Polygon(boundary) if polygonal else LineString(boundary)
            if not shape.is_valid:raise ValueError('Invalid native painted-object geometry: road '+road.attrib['id']+', object '+obj.attrib['id']+', '+str(local))
            region={'kind':kind,'position':[x,y]}
            if polygonal:region['boundary']=boundary
            observations.append({'region':region,'shape':shape,
                'source':{'road_id':int(road.attrib['id']),'object_id':obj.attrib['id'],'object_attributes':dict(obj.attrib),
                          'representation':'polygon' if polygonal else 'zero-width native polyline; paint thickness unobserved',
                          **({'native_centerline':boundary} if not polygonal else {})}})
    return observations



def static_map(path, junctions=False, junction_report=None, native_junction_boxes=(),
               include_non_driving=False, public_way_roads=(), *, partial=False,
               source_roads=None, source_regions=None, cache=None, complete_map=False):
    """Shared hash-keyed static projection; cached results are copied before use."""
    import copy
    import hashlib
    import json
    import pickle
    from pathlib import Path
    params = dict(junctions=junctions, native_junction_boxes=native_junction_boxes,
                  include_non_driving=include_non_driving, public_way_roads=public_way_roads,
                  partial=partial,complete_map=complete_map)
    def build():
        report, sources, identities = [], {}, {}
        result = _static_map(path, junction_report=report, source_roads=sources, source_regions=identities, **params)
        return result, report, sources, identities
    if cache is None:
        value = build()
    else:
        from contextlib import contextmanager
        import fcntl
        @contextmanager
        def locked(path):
            with path.open("a") as stream:
                fcntl.flock(stream,fcntl.LOCK_EX)
                yield
        from .adapter import sha
        signature = hashlib.sha256(json.dumps(['native-map-inventory-v2',sha(path), _SOURCE_SHA,
            _ROADWAYS_SHA, params], sort_keys=True).encode()).hexdigest()
        directory = Path(cache); directory.mkdir(parents=True, exist_ok=True)
        target = directory/(signature+'.pkl')
        with locked(directory/(signature+'.lock')):
            if target.exists():
                with target.open('rb') as stream:value = pickle.load(stream)
            else:
                value = build()
                temporary = target.with_suffix('.tmp')
                with temporary.open('wb') as stream:pickle.dump(value,stream)
                temporary.replace(target)
    result, report, sources, identities = copy.deepcopy(value)
    if junction_report is not None:junction_report.extend(report)
    if source_roads is not None:source_roads.update(sources)
    if source_regions is not None:source_regions.update(identities)
    return result


def match_regions(native, current):
    """Match equivalent geometry regardless of winding, start vertex or sampling.

    No nearest-neighbour identity guess: a second match leaves the source unmapped.
    """
    from shapely.geometry import Polygon, LineString
    from .roadways import boundary_key
    by_key, shapes = {}, {}
    def shape(r):
        b=r.get('boundary')
        if not b or len(b)<2:return None
        value=Polygon(b) if len(b)>=3 else LineString(b)
        return value if value.is_valid and not value.is_empty else None
    for r in current:
        b=r.get('boundary')
        if not b:continue
        key=(r['kind'],boundary_key([tuple(round(x,6) for x in pt) for pt in b]))
        by_key.setdefault(key,[]).append(r['id'])
        value=shape(r)
        if value is not None:shapes.setdefault(r['kind'],[]).append((r['id'],value))
    result={}
    for r in native:
        b=r.get('boundary')
        if not b:continue
        key=(r['kind'],boundary_key([tuple(round(x,6) for x in pt) for pt in b]))
        candidates=by_key.get(key,[])
        if len(candidates)==1:result[r['id']]=candidates[0];continue
        if candidates:continue
        value=shape(r)
        if value is None:continue
        bounds=value.bounds
        candidates=[]
        for ident,other in shapes.get(r['kind'],[]):
            if any(abs(a-b)>1e-5 for a,b in zip(bounds,other.bounds)):continue
            if value.hausdorff_distance(other)<=1e-5:candidates.append(ident)
        if len(candidates)==1:result[r['id']]=candidates[0]
    counts={ident:list(result.values()).count(ident) for ident in set(result.values())}
    return {key:ident for key,ident in result.items() if counts[ident]==1}


def partition_source_roads(native, current, sources, provenance):
    """Join exact native strip intervals by indexed original cross-sections.

    Both ends must be source samples and the whole polygon must equal that
    parameter interval. Conflicting native identities keep membership unknown;
    containment and nearest-neighbour guesses are never used.
    """
    from shapely.geometry import Polygon
    def role(kind):return 'roadway' if kind=='one_way_roadway' else kind
    edges={};regions={}
    for r in current:
        if not r.get('boundary') or len(r['boundary'])<3:continue
        regions[r['id']]=r;vertices=[tuple(round(v,6)for v in p)for p in r['boundary']]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            edges.setdefault((role(r['kind']),frozenset((a,b))),set()).add(r['id'])
    result={}
    for region in native:
        source=sources.get(region['id'],{})
        for samples in [source.get('samples',[]),*source.get('segments',[])]:
            if len(samples)<2:continue
            points=[(station,*[[round(v,6)for v in p]for p in (inner,outer)])for station,inner,outer in samples]
            ends={}
            for i,(_,inner,outer)in enumerate(points):ends.setdefault(frozenset((tuple(inner),tuple(outer))),[]).append(i)
            candidates={}
            for edge,indices in ends.items():
                if len(indices)!=1:continue
                for ident in edges.get((role(region['kind']),edge),()):candidates.setdefault(ident,set()).add(indices[0])
            for ident,indices in candidates.items():
                if len(indices)!=2:continue
                a,b=sorted(indices);boundary=clean_boundary([p[1]for p in points[a:b+1]]+[p[2]for p in reversed(points[a:b+1])])
                if len(boundary)<3:continue
                expected=Polygon(boundary);actual=Polygon(regions[ident]['boundary'])
                if not expected.is_valid or not actual.is_valid or expected.symmetric_difference(actual).area>1e-6:continue
                roads=set(provenance.get(region['id'],[]))
                if ident in result and result[ident]!=roads:result[ident]=set()
                else:result[ident]=roads
    return result


def retained_map(evidence, first, cache=None, inventory=None):
    """Join native map fields by source geometry and explicit public-way IDs."""
    import copy
    import json
    path=evidence.path('road.xodr')
    if path is None:return {}, {}, [], {}, ['Saved map unavailable or not integrity-bound']
    config_path=evidence.path('config.json')
    config=json.loads(config_path.read_text()) if config_path else {}
    from context_catalogue import public_road_ids
    declaration=(inventory or {}).get('authored_road_access')
    public=public_road_ids(path,config,declaration,evidence.used.get('road.xodr'))
    capture=evidence.path('capture/manifest.json')
    manifest=json.loads(capture.read_text()) if capture else {}
    facts_path=evidence.path('capture/'+manifest.get('native_map_facts',{}).get('path','native_map_facts.json'))
    facts=json.loads(facts_path.read_text()) if facts_path else {}
    from .inventory_observations import complete_generated_lanes
    complete=complete_generated_lanes(manifest,facts,evidence.used.get('road.xodr'))
    provenance,issues,region_sources={},[],{}
    try:
        native,polygons,keys=static_map(path,junctions=True,include_non_driving=True,
            public_way_roads=public,native_junction_boxes=facts.get('junctions',[]),
            partial=True,source_roads=provenance,source_regions=region_sources,junction_report=issues,cache=cache,
            complete_map=complete)
    except ValueError as exc:return {}, {}, [], {}, ['Map projection unavailable: '+str(exc)]
    base_remap=match_regions(native,first.get('structures',[]))
    existing={r['id']:r for r in first.get('structures',[])}
    for region in native:
        if region['kind']!='highway' and not region.get('boundary') and region['id'] in existing and existing[region['id']]['kind']==region['kind']:
            base_remap[region['id']]=region['id']
    from .roadways import merge_highways
    merged,group_issues=merge_highways(path,native,polygons,provenance,(declaration or {}).get('way_groups',[]))
    remap=match_regions(native,first.get('structures',[]))
    remap.update({r['id']:r['id'] for r in native if r['kind']!='highway' and not r.get('boundary') and r['id'] in existing and existing[r['id']]['kind']==r['kind']})
    # Original designations and prior exported bindings preserve highway IDs
    # when newly public continuation roads enlarge an existing way.
    existing_way_roads={}
    if declaration and any(r['kind']=='highway' for r in first.get('structures',[])):
        old_sources={}
        old,old_shapes,_=static_map(path,junctions=True,include_non_driving=True,
            public_way_roads=config.get('public_way_road_ids',[]),native_junction_boxes=facts.get('junctions',[]),
            partial=True,source_roads=old_sources,cache=cache,complete_map=complete)
        merge_highways(path,old,old_shapes,old_sources,(declaration or {}).get('way_groups',[]))
        old_matches=match_regions([r for r in old if r['kind']=='highway'],first['structures'])
        existing_way_roads.update({target:set(old_sources[native_id])for native_id,target in old_matches.items()})
        for binding in (inventory or {}).get('highway_bindings',[]):
            ident=binding['region']
            if ident in existing and existing[ident]['kind']=='highway':existing_way_roads[ident]=set(binding['roads'])
    replacements={}
    for r in native:
        if r['kind']!='highway':continue
        roads=set(provenance.get(r['id'],[]))
        candidates=[ident for ident,known in existing_way_roads.items()if known and known<=roads]
        if candidates:
            keep=min(candidates);remap[r['id']]=keep
            replacements.update({ident:keep for ident in candidates if ident!=keep})
    for keep in set(merged.values()):
        members=[keep]+[ident for ident,target in merged.items() if target==keep]
        if all(i in base_remap for i in members):
            remap[keep]=base_remap[keep]
            replacements.update({base_remap[i]:base_remap[keep] for i in members if i!=keep})
    # Add missing observed surfaces only on roads whose full native lane geometry
    # already joins this trace. A cropped/modified lane cannot establish this scope.
    partition_roads=partition_source_roads(native,first.get('structures',[]),region_sources,provenance)
    mapped_roads={road for key,ident in keys.items() if ident in remap for road in [key[0]]}
    next_id=max((r['id'] for r in first.get('structures',[])),default=0)+1
    additions=[]
    for region in native:
        if region['id'] in remap or region['kind'] not in ('highway','shoulder','sidewalk','median_or_divider','bicycle_lane_or_path'):continue
        roads=provenance.get(region['id'],[])
        road_lanes=[ident for key,ident in keys.items() if key[0] in roads]
        if not (declaration and region['kind']=='highway'):
            if not roads or not set(roads)<=mapped_roads or not road_lanes:continue
            if not all(i in remap for i in road_lanes) and (region.get('boundary') or manifest.get('complete_driving_lanes') is not True):continue
        value=copy.deepcopy(region)
        if region.get('boundary') or region['kind']=='highway':value['id']=next_id;next_id+=1
        unknown={k for r in first.get('structures',[]) for k in r.get('unobserved_kinds',[])}-{value['kind']}
        if unknown:value['unobserved_kinds']=sorted(unknown)
        remap[region['id']]=value['id'];additions.append(value)
    highways={}
    for r in native:
        if r['kind']=='highway' and r['id'] in remap:
            for road in provenance.get(r['id'],[]):highways.setdefault(road,[]).append(remap[r['id']])
    fields={}
    for r in native:
        if r['id'] not in remap:continue
        target=remap[r['id']];value={}
        if r['kind']=='highway':
            value['_source_road_ids']=provenance.get(r['id'],[])
            if r['id'] in polygons:value['_way_geometry']=polygons[r['id']]
            current=existing.get(target)
            if current and (r['id'] in merged.values() or declaration):
                measured=r.get('boundary');old_boundary=current.get('boundary')
                if measured is None and old_boundary is not None:value['boundary']=None
                elif measured is not None:
                    from shapely.geometry import Polygon
                    if old_boundary is None or Polygon(old_boundary).hausdorff_distance(Polygon(measured))>1e-5:value['boundary']=measured
        if r.get('lane'):
            lane=copy.deepcopy(r['lane'])
            for key in ('left','right','enters_intersection'):
                if key in lane:
                    if lane[key] in remap:lane[key]=remap[lane[key]]
                    else:lane.pop(key)
            if 'leads_to' in lane:
                if all(i in remap for i in lane['leads_to']):lane['leads_to']=[remap[i] for i in lane['leads_to']]
                else:lane.pop('leads_to')
            value['lane']=lane
            value['_lane_source']=region_sources[r['id']]
        roads=provenance.get(r['id'],[])
        if r['kind']!='highway' and roads and all(road in highways for road in roads):
            value['ways']=sorted({i for road in roads for i in highways[road]})
        if value:fields[target]=value
    for ident,roads in partition_roads.items():
        if roads and all(road in highways for road in roads):fields.setdefault(ident,{})['ways']=sorted({way for road in roads for way in highways[road]})
    # Native painted-object IDs/positions and measured entrance associations
    # supply source road membership for gates absent from the lane-only mesh.
    gate_candidates={}
    for observation in painted_map_objects(path):
        region=observation['region'];position=region.get('position')
        road=observation['source']['road_id']
        if position and road in highways:
            gate_candidates.setdefault((region['kind'],tuple(round(v,6)for v in position)),[]).append(set(highways[road]))
    by_id={r['id']:r for r in first.get('structures',[])}
    for region in first.get('structures',[]):
        if region['kind']not in ('stop_line','crosswalk'):continue
        candidates=gate_candidates.get((region['kind'],tuple(round(v,6)for v in region.get('position',[]))),[])
        if candidates and all(c==candidates[0] for c in candidates):fields.setdefault(region['id'],{})['ways']=sorted(candidates[0]);continue
        entrances=region.get('entrance_of')
        if entrances:
            known=[fields.get(i,{}).get('ways',by_id.get(i,{}).get('ways'))for i in entrances]
            if all(known):fields.setdefault(region['id'],{})['ways']=sorted({replacements.get(w,w)for values in known for w in values})
    if declaration:
        import hashlib
        for group in declaration.get('way_groups',[]):
            targets={way for road in group['roads'] for way in highways.get(road,[])}
            if len(targets)!=1:continue
            for binding in group.get('region_bindings',[]):
                region=by_id.get(binding['region'])
                if region is None:continue
                digest=hashlib.sha256(json.dumps(region.get('boundary'),separators=(',',':')).encode()).hexdigest()
                if region['kind']!=binding['kind']or digest!=binding['boundary_sha256']:raise ValueError('Divided-way region differs from its bound source geometry')
                fields.setdefault(region['id'],{})['ways']=sorted(targets)
    native_lanes={key:remap[ident] for key,ident in keys.items() if ident in remap}
    # Companion source identities, never emitted as Core fields. Coincident XY
    # surfaces from several native regions remain ambiguous, even if flat.
    from .roadways import boundary_key
    sources={}
    for r in native:
        if r['kind'] in ('roadway','one_way_roadway') and r.get('boundary'):
            key=(r['kind'],boundary_key([[round(v,6) for v in p] for p in r['boundary']]))
            sources.setdefault(key,[]).append(r)
    custom=evidence.path('scenario_geometry.json')
    custom=json.loads(custom.read_text()) if custom else {}
    if not custom.get('directed_roadways'):
        for r in first.get('structures',[]):
            if r['kind'] not in ('roadway','one_way_roadway') or not r.get('boundary'):continue
            key=(r['kind'],boundary_key([[round(v,6) for v in p] for p in r['boundary']]))
            matches=sources.get(key,[])
            if len(matches)==1 and provenance.get(matches[0]['id']):
                fields.setdefault(r['id'],{})['_roadway_source']=[evidence.used.get('road.xodr'),
                    provenance[matches[0]['id']],matches[0]['id']]
            elif len(matches)>1:
                records=[region_sources.get(n['id'],{}) for n in matches]
                junctions={v.get('junction',-1) for v in records};heights=[v.get('flat_z') for v in records]
                # Several connector routes may reuse one flat entry surface.
                # This proof requires the same junction, XY boundary and an
                # explicitly constant, equal elevation over each full interval.
                if len(junctions)==1 and next(iter(junctions))>=0 and all(z is not None for z in heights) and max(heights)-min(heights)<=1e-9:
                    fields.setdefault(r['id'],{})['_roadway_source']=[evidence.used.get('road.xodr'),
                        'shared_flat_junction_surface',next(iter(junctions)),heights[0]]
    for ident,value in entrance_geometry_fields(path,first.get('structures',[])).items():
        fields.setdefault(ident,{}).update(value)
    notes=[x['unknown_geometry'] for x in issues if 'unknown_geometry' in x]
    return fields,native_lanes,additions,replacements,notes+group_issues


def entrance_geometry_fields(path, regions):
    """Retain native line geometry for joining gates, without inventing paint area."""
    fields={}
    for observation in painted_map_objects(path):
        native_region=observation['region']
        if native_region['kind']!='stop_line' or 'boundary' in native_region:continue
        matches=[r for r in regions if r['kind']=='stop_line' and r.get('position')
                 and math.dist(r['position'],native_region['position'])<=1e-5]
        if len(matches)==1:
            value=fields.setdefault(matches[0]['id'],{})
            value['_unobserved_paint_boundary']=True
            value['_entrance_geometry']=observation['source']['native_centerline']
            value['_entrance_road']=observation['source']['road_id']
    return fields


def lane_segments(scene, fields):
    """Plan a stable, sampled partition of lanes without one constant heading.

    Every piece uses the original map samples, so its union is the old footprint.
    Directions are local chord estimates, never a heading borrowed from a vehicle.
    The first piece in travel order retains the original ID; later pieces get new
    IDs. All pieces remain approaches to the original intersection, if known.
    """
    import copy
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    originals={r['id']:r for r in scene.get('structures',[])}
    next_id=max(originals,default=0)+1
    result={};issues=[]
    scoped={i['target'] for i in scene.get('intents',[])}
    for ident,original in originals.items():
        patch=fields.get(ident,{})
        lane=dict(original.get('lane',{}));lane.update(patch.get('lane',{}))
        source=patch.get('_lane_source')
        if original['kind']!='lane' or lane.get('direction') is not None or not source:continue
        if ident in scoped:
            issues.append('Lane '+str(ident)+' has a scoped intention target; its plan requires an explicit segment binding')
            continue
        # Trace coordinates are rounded at export. Reuse those exact vertices
        # when the source sample matches, avoiding tiny slivers on subdivision.
        vertices={tuple(round(v,6) for v in p):p for p in original['boundary']}
        samples=[[s,*[vertices.get(tuple(round(v,6) for v in p),p) for p in (inner,outer)]]
                 for s,inner,outer in source['samples']]
        pairs=list(zip(samples,samples[1:]))
        if source['lane_id']>0:pairs.reverse()
        pieces=[]
        for a,b in pairs:
            boundary=clean_boundary([a[1],b[1],b[2],a[2]])
            shape=Polygon(boundary)
            if not shape.is_valid or shape.area<=1e-8:break
            vector=[sum(b[k][j]-a[k][j] for k in (1,2))/2 for j in (0,1)]
            norm=math.hypot(*vector)
            if norm<=1e-9:break
            direction=[v/norm*(-1 if source['lane_id']>0 else 1) for v in vector]
            value=copy.deepcopy(original);value['boundary']=boundary
            value['lane']=dict(copy.deepcopy(lane),direction=direction)
            value['id']=ident if not pieces else next_id
            if pieces:next_id+=1
            pieces.append((value,(a[0],b[0])))
        if len(pieces)!=len(pairs) or not pieces:
            issues.append('Lane '+str(ident)+' has a degenerate native segment; full footprint retained with unknown direction')
            continue
        union=unary_union([Polygon(p['boundary']) for p,_ in pieces])
        if union.symmetric_difference(Polygon(original['boundary'])).area>1e-6:
            issues.append('Lane '+str(ident)+' does not partition its retained footprint exactly; not split')
            continue
        result[ident]=pieces
    for ident,pieces in result.items():
        for index,(piece,interval) in enumerate(pieces):
            lane=piece['lane']
            if index+1<len(pieces):lane['leads_to']=[pieces[index+1][0]['id']]
            for key in ('left','right'):
                target=lane.get(key)
                if target not in result:continue
                candidates=[p['id'] for p,span in result[target] if span==interval]
                if len(candidates)==1:lane[key]=candidates[0]
                else:lane.pop(key)  # No scalar neighbour assertion across unequal cuts.
    return result,issues


def compile_lane_segments(segments, fields=None):
    from shapely.geometry import Polygon,LineString
    from shapely.strtree import STRtree
    shapes={p['id']:Polygon(p['boundary']) for pieces in segments.values() for p,_ in pieces}
    fields=fields or {}
    entrances={ident:LineString(v['_entrance_geometry']) for ident,v in fields.items() if v.get('_entrance_geometry')}
    sources={ident:v['_lane_source']['road_id'] for ident,v in fields.items() if v.get('_lane_source')}
    connections={ident:{sources[target] for target in v.get('lane',{}).get('leads_to',[]) if target in sources}
                 for ident,v in fields.items() if v.get('lane')}
    return {'shapes':shapes,'tree':STRtree(list(shapes.values())),'identities':list(shapes),
        'entrances':entrances,'entrance_roads':{ident:v['_entrance_road'] for ident,v in fields.items() if '_entrance_road' in v},
        'connections':connections}


def project_lane_segments(scene, segments, compiled=None, observed_footprints=None):
    """Relink a static lane partition and recompute only its body overlaps."""
    import copy
    from shapely.geometry import Polygon,Point
    if not segments:return 0
    if any(i['target'] in segments for i in scene.get('intents',[])):
        raise ValueError('Scoped lane intention needs an explicit segment target')
    compiled=compiled if compiled is not None else compile_lane_segments(segments)
    shapes=compiled['shapes'];tree=compiled['tree'];identities=compiled['identities'];entrances=compiled['entrances']
    original={r['id']:r for r in scene['structures']}
    # Partition templates predate per-frame inventory and membership projection.
    # Preserve those current classifications; replace only partition geometry/IDs
    # and the lane fields whose references/direction depend on the subdivision.
    scene['structures']=[p for r in scene['structures'] for p in
        ([dict(copy.deepcopy(r),id=p['id'],boundary=copy.deepcopy(p['boundary']),
               lane=copy.deepcopy(p['lane'])) for p,_ in segments[r['id']]]
         if r['id'] in segments else [r])]
    def expanded(ids):return list(dict.fromkeys(p['id'] for ident in ids for p,_ in segments.get(ident,[(original[ident],None)])))
    for region in scene['structures']:
        if region.get('entrance_of') is not None:
            targets=region['entrance_of'];shape=None
            if region['id'] in entrances:shape=entrances[region['id']]
            elif region.get('boundary'):shape=Polygon(region['boundary'])
            elif region.get('position'):shape=Point(region['position'])
            if any(i in segments for i in targets):
                if shape is None:raise ValueError('Segmented lane entrance has no measured geometry')
                associated=[i for i in expanded(targets) if i not in shapes or shapes[i].distance(shape)<=1e-5]
                # Native stop lines can lie just inside a junction connector,
                # beyond the incoming lane's crop. Preserve its existing gate
                # association on the terminal piece only when explicit native
                # connectivity joins that lane to the object's source road.
                if region['kind']=='stop_line' and region['id'] in compiled['entrance_roads']:
                    road=compiled['entrance_roads'][region['id']]
                    for target in targets:
                        if target in segments and not any(p['id'] in associated for p,_ in segments[target]):
                            if road in compiled['connections'].get(target,set()):associated.append(segments[target][-1][0]['id'])
                region['entrance_of']=list(dict.fromkeys(associated))
                if not region['entrance_of']:raise ValueError('Measured entrance does not meet any lane segment')
    for device in scene.get('devices',[]):
        if device.get('governs') is not None:device['governs']=expanded(device['governs'])
    scene['occupies']=[pair for pair in scene.get('occupies',[]) if pair[1] not in segments]
    for user in scene.get('users',[]):
        if user['track'] in (observed_footprints or {}):
            body_shape=observed_footprints[user['track']]
            scene['occupies'].extend([user['track'],identities[int(i)]] for i in sorted(tree.query(body_shape,predicate='intersects')))
            continue
        kin=user.get('kin',{});pos=kin.get('position');heading=kin.get('heading');extent=kin.get('extent')
        if pos is None or heading is None or extent is None or math.hypot(*heading)<=1e-9:
            scene['occupancy_observed']=[t for t in scene.get('occupancy_observed',[]) if t!=user['track']]
            continue
        norm=math.hypot(*heading);fx,fy=[v/norm for v in heading]
        body_shape=Polygon([[pos[0]+a*extent[0]*fx-b*extent[1]*fy,pos[1]+a*extent[0]*fy+b*extent[1]*fx]
            for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]])
        scene['occupies'].extend([user['track'],identities[int(i)]] for i in sorted(tree.query(body_shape,predicate='intersects')))
    return sum(len(pieces) for pieces in segments.values())
