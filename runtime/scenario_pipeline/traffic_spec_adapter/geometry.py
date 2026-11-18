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


STRIP_SAMPLING_ERROR_M = 0.001


def normalized_polygon(points):
    """Remove exact ring redundancy, then validate the serialized coordinates."""
    from shapely.geometry import Polygon
    result=[]
    for point in points:
        if len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):
            raise ValueError('Nonfinite or malformed polygon coordinate')
        value=list(point)
        if not result or value!=result[-1]:result.append(value)
    if len(result)>1 and result[0]==result[-1]:result.pop()
    polygon=Polygon(result) if len(result)>=3 else None
    if polygon is None or not polygon.is_valid or polygon.area<=0 or polygon.interiors:
        raise ValueError('Geometry is not one valid simple area polygon')
    return result


def strip_polygon(points, total_width):
    """One symmetric estimated strip: flat caps, bevel joins, no hull repair."""
    from shapely.geometry import LineString
    if type(total_width) not in (int,float) or not math.isfinite(total_width) or total_width<=0:
        raise ValueError('Strip width must be finite and positive')
    source=[]
    for point in points:
        if len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point):
            raise ValueError('Invalid strip reference coordinate')
        if not source or list(point)!=source[-1]:source.append(list(point))
    if len(source)<2:raise ValueError('Strip reference needs two distinct points')
    line=LineString(source)
    if not line.is_simple or line.is_ring:raise ValueError('Unsupported branching/crossing/closed strip reference')
    shape=line.buffer(total_width/2,cap_style=2,join_style=3)
    if shape.geom_type!='Polygon' or shape.interiors or not shape.is_valid:
        raise ValueError('Strip has no single simple-polygon representation')
    boundary=normalized_polygon([[round(v,6) for v in point] for point in shape.exterior.coords])
    return boundary, {'total_width_m':total_width,'half_width_m':total_width/2,
        'caps':'flat','joins':'bevel','coordinate_quantization_m':0.000001,
        'reference_points':source,'reference_kind':'retained_polyline',
        'unsampled_curve_error':'unknown unless an analytic sampling bound is supplied'}


def lane_marking(source_lane, *, complete=False, station=None):
    """Map explicit paint, or verified no paint in a complete generated map.

    ``other`` is the non-white/yellow colour tag for an absent painted line;
    it is never substituted for an unavailable colour on an existing line.
    """
    marks=source_lane.findall('roadMark') if source_lane is not None else []
    if not marks:return ['none','other'] if complete else None
    if station is not None:
        marks=[m for m in marks if float(m.get('sOffset',0)) <= station]
        if not marks:return None
        marks=[max(marks,key=lambda m:float(m.get('sOffset',0)))]
    values={(m.get('type'),m.get('color')) for m in marks}
    kinds={'broken':'broken','solid':'solid','solid solid':'double_solid',
           'solid broken':'solid_broken','broken solid':'solid_broken',
           'botts dots':'dotted','curb':'curb','none':'none'}
    if len(values)!=1 or (station is None and float(marks[0].get('sOffset',0))!=0):return None
    typ,color=next(iter(values))
    if typ not in kinds:return None
    if color in ('white','yellow'):return [kinds[typ],color]
    if typ=='none' or color in ('blue','green','red','orange','other','none'):
        return [kinds[typ],'other']
    return None


def constant_offset_surface(geometries, start, end, offsets, error_m=.001):
    """Image of a constant-width line/arc surface, split at its analytic folds."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    if type(error_m)not in (int,float)or not math.isfinite(error_m)or error_m<=0:
        raise ValueError('Analytic surface error budget must be finite and positive')
    if len(offsets)!=2 or any(type(v)not in (int,float)or not math.isfinite(v)for v in offsets):
        raise ValueError('Analytic surface requires two finite offsets')
    pieces=[];folds=0;bound=0.;samples=0;seam_bound=0.;unresolved_seams=[]
    for geometry_index,geometry in enumerate(geometries):
        origin=float(geometry.get('s'));low=max(start,origin)
        high=min(end,origin+float(geometry.get('length')))
        if high<=low:continue
        arc=geometry.find('arc')
        if geometry.find('line')is None and arc is None:raise ValueError('Unsupported analytic surface geometry')
        curvature=float(arc.get('curvature'))if arc is not None else 0.
        second=abs(curvature)*max(abs(1-curvature*t)for t in offsets)
        step=min(2.,math.sqrt(8*(error_m/2)/second))if second else 2.
        count=max(1,math.ceil((high-low)/step));samples+=count+1
        bound=max(bound,second*((high-low)/count)**2/8)
        seam=None
        if geometry_index+1<len(geometries):
            following=geometries[geometry_index+1]
            if abs(float(following.get('s'))-high)<=1e-9:
                x,y,h,_=reference(geometry,high);nx,ny,nh,_=reference(following,float(following.get('s')))
                old=[[x-math.sin(h)*t,y+math.cos(h)*t]for t in offsets]
                new=[[nx-math.sin(nh)*t,ny+math.cos(nh)*t]for t in offsets]
                displacement=max(math.dist(a,b)for a,b in zip(old,new))
                if displacement<=error_m/2:
                    seam=(nx,ny,nh);seam_bound=max(seam_bound,displacement)
                else:unresolved_seams.append({'station':high,'displacement_m':displacement})
        def edge(station,offset):
            x,y,h,_=reference(geometry,station)
            if seam is not None and abs(station-high)<=1e-10:x,y,h=seam
            return[x-math.sin(h)*offset,y+math.cos(h)*offset]
        folded=curvature!=0 and min(offsets)<1/curvature<max(offsets)
        if folded:
            # One identical source point for every fan triangle on this arc.
            x,y,h,_=reference(geometry,origin)
            center=[x-math.sin(h)/curvature,y+math.cos(h)/curvature]
        for i in range(count):
            a=low+i*(high-low)/count;b=low+(i+1)*(high-low)/count
            if folded:
                parts=[Polygon([edge(a,t),edge(b,t),center])for t in offsets];folds+=1
            else:parts=[Polygon([edge(a,offsets[0]),edge(b,offsets[0]),edge(b,offsets[1]),edge(a,offsets[1])])]
            if any(not p.is_valid or p.area<=0 for p in parts):raise ValueError('Invalid analytic surface part')
            pieces.extend(parts)
    return unary_union(pieces),{'method':'constant_offset_analytic_arc_fold_split',
        'offsets_m':list(offsets),'fold_intervals':folds,'source_samples':samples,
        'max_chord_deviation_m':bound,'chord_deviation_budget_m':error_m/2,
        'max_source_seam_displacement_m':seam_bound,'source_seam_displacement_budget_m':error_m/2,
        'combined_geometry_error_budget_m':error_m,'unresolved_source_seams':unresolved_seams,
        'source_seam_policy':'following native primitive start is canonical only within the declared displacement budget',
        'serialized_coordinate_precision_m':1e-6,
        'construction':'source curvature-centre triangle fans at Jacobian-zero offset; ordinary station quadrilaterals elsewhere'}


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
            stations=sorted(set(stations+[float(v.get('s'))for v in road.findall('./lanes/laneOffset')if start<float(v.get('s'))<end]+
                [start+float(v.get('sOffset'))for lane in lanes for v in lane.findall('width')if start<start+float(v.get('sOffset'))<end]))
            marking_lanes=lanes+[section.find('./center/lane')]
            stations=sorted(set(stations+[start+float(m.get('sOffset',0))
                for source_lane in marking_lanes if source_lane is not None
                for m in source_lane.findall('roadMark')
                if start<start+float(m.get('sOffset',0))<end]))
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
                    highway_method=None
                    width_records=[l.findall('width')for l in lanes if int(l.get('id'))!=0]
                    offset_records=road.findall('./lanes/laneOffset')
                    def constant_records(records):
                        return (all(float(record.get(k,'0'))==0 for record in records for k in ('b','c','d'))
                            and (not records or max(float(v.get('a','0'))for v in records)-min(float(v.get('a','0'))for v in records)<=1e-9))
                    constant=constant_records(offset_records)and all(records and constant_records(records)for records in width_records)
                    x,y,h,_=reference(next(g for g in reversed(geoms)if float(g.get('s'))<=start+1e-9),start)
                    outer=[edge(start,left,bool(pos)),edge(start,right,bool(neg))]
                    offsets=[-(p[0]-x)*math.sin(h)+(p[1]-y)*math.cos(h)for p in outer]
                    folded=constant and any(g.find('arc')is not None and float(g.find('arc').get('curvature'))!=0 and
                        min(offsets)<1/float(g.find('arc').get('curvature'))<max(offsets)for g in geoms
                        if float(g.get('s'))<end and float(g.get('s'))+float(g.get('length'))>start)
                    if folded:
                        polygon,highway_method=constant_offset_surface(geoms,start,end,offsets)
                        highway_method['constant_record_tolerance_m']=1e-9
                        highway_method['source_offset_variation_bound_m']=sum(
                            max(float(v.get('a','0'))for v in records)-min(float(v.get('a','0'))for v in records)
                            for records in [offset_records]+width_records if records)
                        # Apply the final trace coordinate grid to the surface
                        # before extracting its ring; rounding a ring alone can
                        # retain zero-length seams at analytic joins.
                        from shapely import set_precision
                        polygon=set_precision(polygon,1e-6)
                        highway_method['surface_coordinate_grid_m']=1e-6
                    elif not polygon.is_valid or polygon.area<=0:
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
                        try:region['boundary']=normalized_polygon([[round(v,6)for v in p]for p in polygon.exterior.coords])
                        except ValueError:pass
                    if 'boundary'not in region and junction_report is not None:
                        junction_report.append({'unknown_geometry':'Public road '+str(rid)+' has no single simple Core boundary; occupancy uses the source surface only where established'})
                    regions.append(region)
                    if highway_method and source_regions is not None:
                        source_regions[ident]={'road_id':rid,'section':section_index,'highway_geometry_method':highway_method}
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
                marking_intervals={}
                for side,source_lane in [('left',inner),('right',lane)]:
                    value=lane_marking(source_lane,complete=complete_map)
                    if value is not None:info['marking_'+side]=value
                    # Missing map declarations do not disprove an independently
                    # recorded marking. Explicit source records still govern their intervals.
                    if complete_map or (source_lane is not None and source_lane.findall('roadMark')):
                        marking_intervals[side]=[[a,b,lane_marking(source_lane,complete=complete_map,station=(a+b)/2-start)]
                            for a,b in zip(stations,stations[1:])]
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
                        'samples':[[s,edge(s,lid,False),edge(s,lid,True)] for s in stations],
                        'entry_topology_complete':bool(complete_map and junctions),'entry_junctions':[],
                        'marking_intervals':marking_intervals}
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
                if source_regions is not None:
                    source_regions[ident]={'junction_id':jid,'component':len(emitted)-1}
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
                    if source_regions is not None and key in keys:
                        info=source_regions.get(keys[key],{})
                        info['entry_junctions']=sorted(set(info.get('entry_junctions',[]))|{jid})
                    if key not in keys or target_id is None:continue
                    lane=by_id[keys[key]]['lane']
                    lane['leads_to']=sorted(set(lane.get('leads_to',[])+[target_id]))
                    # A scalar Core reference cannot represent several disconnected
                    # intersection components. Only attach an unambiguous region.
                    matches=[i for i in junction_regions.get(jid,[]) if polygons[i].intersects(polygons[target_id])]
                    if len(matches)==1:
                        lane['enters_intersection']=matches[0]
    if source_regions is not None:
        for (rid,section,lid),ident in keys.items():
            direction='successor' if lid<0 else 'predecessor'
            road=roads[rid];sections=road.findall('./lanes/laneSection')
            endpoint=section==(len(sections)-1 if lid<0 else 0)
            link=road.find('./link/'+direction)
            info=source_regions.get(ident,{})
            if endpoint and link is not None and link.get('elementType')=='junction' and not info.get('entry_junctions'):
                info['entry_topology_complete']=False
    if source_regions is not None:
        native_by_id={r['id']:r for r in regions}
        for ident in keys.values():
            info=source_regions.get(ident,{})
            # Keep immediate source topology even when a retained Core trace
            # does not have a matching connector region identity.
            info['native_continuations']=[{key:source_regions[target][key]
                for key in ('road_id','section','lane_id','samples')}
                for target in native_by_id[ident].get('lane',{}).get('leads_to',[])
                if target in source_regions and 'samples' in source_regions[target]]
    return regions,polygons,keys


def source_lane_direction(road, lane):
    """OpenDRIVE side/rule defaults plus explicit direction; no name heuristic."""
    if lane.get('dynamicLaneDirection','false').lower() not in ('false','no','0'):return None
    direction=lane.get('direction','standard').lower();rule=road.get('rule','RHT').upper()
    if direction not in ('standard','reversed') or rule not in ('RHT','LHT'):return None
    ident=int(lane.get('id'))
    if ident==0:return None
    sign=(-1 if ident>0 else 1)*(1 if rule=='RHT' else -1)
    return sign*(-1 if direction=='reversed' else 1)


def native_centre_lines(path):
    """Estimated 1 cm total-width dividers between opposing driving lanes.

    The reference direction is OpenDRIVE increasing s. Lane offsets are retained.
    A one-way road has no opposing-direction divider. Paint attributes remain
    source evidence; the polyline never invents a painted width or legal zone.
    """
    observations=[]
    for road in ET.parse(path).getroot().findall('road'):
        sections=road.findall('./lanes/laneSection');geoms=road.findall('./planView/geometry')
        for index,section in enumerate(sections):
            left=section.findall("./left/lane[@type='driving']");right=section.findall("./right/lane[@type='driving']")
            if not left or not right:continue
            left_directions={source_lane_direction(road,lane) for lane in left}
            right_directions={source_lane_direction(road,lane) for lane in right}
            if None in left_directions|right_directions or len(left_directions)!=1 or len(right_directions)!=1:continue
            if left_directions==right_directions:continue
            start=float(section.attrib['s'])
            end=float(sections[index+1].attrib['s']) if index+1<len(sections) else float(road.attrib['length'])
            offsets=road.findall('./lanes/laneOffset')
            breaks=sorted({start,end}|{float(g.attrib['s']) for g in geoms+offsets
                                      if start<float(g.attrib['s'])<end})
            stations=[];sampling_bound=0.
            for low,high in zip(breaks,breaks[1:]):
                g=next(g for g in reversed(geoms) if float(g.attrib['s'])<=low+1e-9)
                arc=g.find('arc');k=abs(float(arc.attrib['curvature'])) if arc is not None else 0.
                eligible=[node for node in offsets if float(node.attrib['s'])<=low+1e-9]
                offset=eligible[-1] if eligible else None
                coefficients=[float(offset.attrib.get(c,0)) if offset is not None else 0. for c in 'abcd']
                dmax=max(0.,high-float(offset.attrib['s'])) if offset is not None else 0.
                bounds=[sum(abs(coefficients[i])*math.factorial(i)/math.factorial(i-order)*dmax**(i-order)
                            for i in range(order,4)) for order in range(3)]
                # For r=reference+offset*normal on a line/constant-curvature arc:
                # |r''| <= |k|+|offset''|+2|k offset'|+k²|offset|.
                second=k+bounds[2]+2*k*bounds[1]+k*k*bounds[0]
                step=min(2.,math.sqrt(8*STRIP_SAMPLING_ERROR_M/second)) if second else 2.
                count=max(1,math.ceil((high-low)/step))
                sampling_bound=max(sampling_bound,second*((high-low)/count)**2/8)
                stations.extend(low+i*(high-low)/count for i in range(count))
            stations.append(end)
            boundary=[]
            for station in stations:
                g=next(g for g in reversed(geoms)if float(g.attrib['s'])<=station+1e-9)
                x,y,h,_=reference(g,station)
                offset=polynomial(road.findall('./lanes/laneOffset'),station)
                boundary.append([x-math.sin(h)*offset,y+math.cos(h)*offset])
            from shapely.geometry import Polygon
            reference_line=boundary
            boundary,method=strip_polygon(reference_line,0.01)
            method.update(reference_kind='sampled_analytic_opendrive_line_or_arc_with_cubic_offset',
                          max_reference_deviation_m=sampling_bound,
                          reference_deviation_budget_m=STRIP_SAMPLING_ERROR_M,
                          unsampled_curve_error='bounded by the analytic second-derivative chord bound')
            observations.append({'region':{'kind':'centre_line','boundary':boundary},'shape':Polygon(boundary),
                'source':{'road_id':int(road.attrib['id']),'section_id':index,'method':'estimated_centreline_buffer_1cm','native_centerline':reference_line,
                          'geometry_method':method,
                          'centre_road_marks':[dict(mark.attrib)for mark in section.findall('./center/lane/roadMark')],
                          'direction_contract':{'road_rule':road.get('rule','RHT'),'left':sorted(left_directions),'right':sorted(right_directions),'method':'OpenDRIVE side/rule plus explicit direction overrides'},
                          'scope':'Geometric divider; paint visibility and legal interpretation are not inferred'}})
    return observations


def painted_map_objects(path, verified_stop_lines=()):
    """Native OpenDRIVE StopLine/crosswalk objects, with no invented paint width.

    Unverified zero-width StopLine objects remain line segments. Only a validated
    static-inventory paint/reference binding enables the symmetric 35 cm estimate.
    Measured area outlines always take precedence; no width is inferred from a name.
    """
    from shapely.geometry import Polygon, LineString, Point
    verified = {(b['road_id'], b['object_id']): b for b in verified_stop_lines}
    if len(verified) != len(verified_stop_lines):
        raise ValueError('Duplicate verified painted-stop-line identity')
    observed_bindings = set()
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
            # An explicit area outline is independent of the optional width
            # attribute. Never discard observed corners because width is zero.
            chord=LineString([local[0],local[-1]])
            line_like=(chord.length>0 and LineString(local).is_simple and
                       all(chord.distance(Point(point))<=1e-8 for point in local))
            polygonal=kind!='stop_line' or float(obj.attrib.get('width',0))>1e-8 or (bool(corners) and not line_like)
            if polygonal:
                try:boundary=normalized_polygon(boundary)
                except ValueError as exc:
                    raise ValueError('Invalid native '+kind+' outline: road '+road.attrib['id']+', object '+obj.attrib['id']+': '+str(exc))from exc
            shape=Polygon(boundary) if polygonal else LineString(boundary)
            if not shape.is_valid:raise ValueError('Invalid native painted-object geometry: road '+road.attrib['id']+', object '+obj.attrib['id']+', '+str(local))
            source={'road_id':int(road.attrib['id']),'object_id':obj.attrib['id'],'object_attributes':dict(obj.attrib),
                    'representation':'polygon' if polygonal else 'zero-width native polyline; paint thickness unobserved',
                    **({'native_centerline':boundary,'outline_linear_tolerance_m':1e-8} if not polygonal else {})}
            key=(source['road_id'],source['object_id'])
            if key in verified:
                if kind!='stop_line':raise ValueError('Paint verification names a different reference kind')
                if key in observed_bindings:raise ValueError('Duplicate source painted-stop-line identity')
                observed_bindings.add(key)
                if not polygonal:
                    boundary,method=strip_polygon(source['native_centerline'],0.35)
                    shape=Polygon(boundary);polygonal=True
                    source.update(representation='estimated painted-stop-line polygon',
                        geometry_method='estimated_verified_stop_line_strip_35cm',
                        strip_method=method,paint_verification=verified[key])
            region={'kind':kind,'position':[x,y]}
            if polygonal:region['boundary']=boundary
            observations.append({'region':region,'shape':shape,'source':source})
    if set(verified)!=observed_bindings:
        raise ValueError('Verified painted stop line missing from source map')
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
        # GEOS Hausdorff distance can be undefined for valid rings containing
        # zero-length edges. Remove exact adjacent duplicates only in this
        # temporary comparison view; retained/native boundary bytes stay intact.
        clean=[]
        for point in b:
            if not clean or point!=clean[-1]:clean.append(point)
        polygonal=len(b)>=3
        if len(clean)<(3 if polygonal else 2):return None
        value=Polygon(clean) if polygonal else LineString(clean)
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


def partition_source_roads(native, current, sources, provenance, *, lane_sources=None):
    """Join exact native strip intervals by indexed original cross-sections.

    Both ends must be source samples and the whole polygon must equal that
    parameter interval. Conflicting native identities keep membership unknown;
    containment and nearest-neighbour guesses are never used.
    """
    import copy
    from shapely.geometry import Polygon
    def role(kind):return 'roadway' if kind=='one_way_roadway' else kind
    edges={};regions={}
    for r in current:
        if not r.get('boundary') or len(r['boundary'])<3:continue
        regions[r['id']]=r;vertices=[tuple(round(v,6)for v in p)for p in r['boundary']]
        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
            edges.setdefault((role(r['kind']),frozenset((a,b))),set()).add(r['id'])
    result={};lane_matches={}
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
                if region['kind']=='lane' and {'road_id','section','lane_id'}<=source.keys():
                    # Same road is insufficient: the lane and exact source
                    # station interval must also have one unambiguous identity.
                    observed=copy.deepcopy(source)
                    observed['samples']=copy.deepcopy(samples[a:b+1])
                    observed.pop('segments',None);observed.pop('native_continuations',None)
                    matches=lane_matches.setdefault(ident,[])
                    if observed not in matches:matches.append(observed)
    if lane_sources is not None:
        for ident,matches in lane_matches.items():
            if len(matches)==1 and result.get(ident):lane_sources[ident]=matches[0]
    return result


def canonical_junctions(regions, native, sources, bindings, map_sha256, preferred=()):
    """Merge only explicitly source-bound copies of one native component."""
    from shapely.geometry import Polygon
    from .roadways import compatible_properties
    current={r['id']:r for r in regions};groups={};replacements={}
    native_keys={(source['junction_id'],source['component']):r for r in native
                 if (source:=sources.get(r['id'],{})).get('junction_id') is not None}
    for binding in bindings:
        if binding.get('map_sha256')!=map_sha256:raise ValueError('Junction binding belongs to another map')
        ident=binding['region'];key=(binding['junction_id'],binding['component'])
        original=current.get(ident);reference=native_keys.get(key)
        if original is None or reference is None or original['kind']!='intersection':
            raise ValueError('Junction binding has no matching source component')
        if not original.get('boundary') or not reference.get('boundary'):
            raise ValueError('Junction component boundary unavailable')
        a,b=Polygon(original['boundary']),Polygon(reference['boundary'])
        if not a.is_valid or not b.is_valid or a.symmetric_difference(b).area>1e-6:
            raise ValueError('Junction binding contradicts native component geometry')
        if any(ident in members for members in groups.values()):raise ValueError('Duplicate junction binding')
        groups.setdefault(key,[]).append(ident)
    for members in groups.values():
        keep=min(members,key=lambda ident:(ident not in preferred,ident));combined=current[keep]
        for ident in sorted(set(members)-{keep}):
            combined=compatible_properties(combined,current[ident])
            if combined is None:raise ValueError('Source junction copies have conflicting properties')
            replacements[ident]=keep
    return replacements


def bound_junction_source_fields(components, road_sources, bindings, replacements):
    """Consume already validated component bindings and canonical choices."""
    fields={}
    for binding in bindings:
        reference=components[(binding['junction_id'],binding['component'])]
        roads=road_sources.get(reference)
        if not roads:raise ValueError('Bound junction lacks source-road height scope')
        ident=replacements.get(binding['region'],binding['region'])
        value={'_source_road_ids':sorted(set(roads)),
               '_verified_structure_kinds':['intersection']}
        if ident in fields and fields[ident]!=value:
            raise ValueError('Conflicting bound junction source identities')
        fields[ident]=value
    return fields



def reviewed_intersection_source_fields(evidence, regions, native, sources, road_sources, map_sha256):
    """Consume a strict physical-roadway review without replacing its boundary."""
    import json
    from shapely.geometry import Polygon
    from .scenario_geometry import retained_review
    review=retained_review(evidence)
    if review is None:return {}
    path=evidence.path(review['review'])
    if path is None:raise ValueError('Reviewed intersection document is not bound to original evidence')
    document=json.loads(path.read_text())
    if document.get('schema')!='reviewed-roadway-intersection-boundary-v1':return {}
    if (document.get('map_sha256')!=map_sha256 or
            document.get('sources',{}).get('road.xodr')!=map_sha256 or
            document.get('rendered_review_confirmed') is not True):
        raise ValueError('Reviewed intersection requires its bound map and confirmed physical review')
    for name,digest in document['sources'].items():
        if evidence.path(name) is None or evidence.used.get(name)!=digest:
            raise ValueError('Reviewed intersection source is not bound to original evidence: '+name)
    boundary=normalized_polygon(document.get('boundary_core_m'))
    physical=Polygon(boundary)
    candidates=[r for r in regions if r['kind']=='intersection' and r.get('boundary')
                and Polygon(normalized_polygon(r['boundary'])).equals(physical)]
    if len(candidates)!=1:
        raise ValueError('Reviewed physical boundary has no unique exact retained identity')
    # The coarse native reference identifies source roads for the EXISTING
    # height gate; it neither defines nor limits the reviewed physical outline.
    roads=[]
    if document.get('native_junction_box_m') is not None:
        reference=Polygon(normalized_polygon(document['native_junction_box_m']))
        components=[r for r in native if sources.get(r['id'],{}).get('junction_id') is not None
                    and r.get('boundary') and Polygon(normalized_polygon(r['boundary'])).equals(reference)]
        if len(components)!=1:raise ValueError('Reviewed native reference has no unique exact source component')
        roads=road_sources.get(components[0]['id'],[])
    return {candidates[0]['id']:{'_source_road_ids':sorted(set(roads)),
                                '_verified_structure_kinds':['intersection']}}


def retained_obstruction_fields(evidence, first, inventory):
    """Consume measured vertices under the existing complete physical contract."""
    import json
    from shapely.geometry import MultiPoint
    from .roadways import boundary_key
    from .inventory_observations import validate_kind_inventory
    contract=(inventory or {}).get('kind_inventory_contracts',{}).get('obstruction')
    if not contract:return {}
    validate_kind_inventory(evidence,inventory,'obstruction',inventory['kinds']['obstruction'])
    document=json.loads(evidence.path(contract['physical_inventory_source']).read_text())
    current={r['id']:r for r in first.get('structures',[])}
    objects={o['id']:o for o in document['objects']};result={};shapes={}
    from .occupancy import native_single_plane
    import xml.etree.ElementTree as ET
    map_path=evidence.path('road.xodr')
    plane=float(ET.parse(map_path).getroot().find('./road/elevationProfile/elevation').get('a'))if native_single_plane(map_path)else None
    original_frames={r['frame']for r in evidence.rows('trace.jsonl')}
    frame_sources=[r for r in evidence.rows('capture/native/frames.jsonl')if r.get('frame')in original_frames]
    if len(frame_sources)!=len(original_frames)or {r['frame']for r in frame_sources}!=original_frames:
        raise ValueError('Obstruction geometry needs every original graph frame')
    required_graph_sources={'capture/native/frames.jsonl'}|{'capture/native/'+r['base']for r in frame_sources}
    for instance in contract['instances']:
        obj=objects[instance['object_id']];geometry=obj.get('geometry')
        if geometry is None:continue
        vertices=geometry.get('vertices_native_m');proof=geometry.get('evidence',{})
        if (instance['kind']!='obstruction' or geometry.get('method')!='native_actor_world_vertices_v1'
                or type(obj['id'])is not int or geometry.get('actor_id')!=obj['id']
                or not isinstance(geometry.get('native_name'),str)or not geometry['native_name']
                or not proof or not required_graph_sources<=set(proof)
                or any(inventory['evidence'].get(n)!=h for n,h in proof.items())
                or not isinstance(vertices,list)or len(vertices)!=8
                or any(not isinstance(p,list)or len(p)!=3 or any(type(v)not in(int,float)or not math.isfinite(v)for v in p)for p in vertices)):
            raise ValueError('Obstruction geometry lacks bound finite original actor vertices')
        shape=MultiPoint([(x,-y)for x,y,z in vertices]).convex_hull
        if shape.geom_type!='Polygon' or not shape.is_valid or shape.area<=0:
            raise ValueError('Obstruction world vertices have no valid occupied area')
        key=boundary_key([[round(x,6),round(y,6)]for x,y in list(shape.exterior.coords)[:-1]])
        if key in shapes:raise ValueError('Coincident physical obstruction actors are ambiguous')
        shapes[key]=obj['id'];ident=instance['region'];region=current.get(ident)
        matches=[r['id']for r in current.values()if r['kind']=='obstruction'and r.get('boundary')and boundary_key(r['boundary'])==key]
        if region is None or region['kind']!='obstruction' or matches!=[ident]:
            raise ValueError('Physical obstruction differs from its unique retained source area')
        result[ident]={'_verified_structure_kinds':['obstruction'],'_obstruction_geometry_source':{
            'method':'native_actor_world_vertices_v1','actor_id':obj['id'],'native_name':geometry['native_name'],
            'native_plane_height_m':plane,'vertices_native_m':vertices,'vertical_range_m':[min(p[2]for p in vertices),max(p[2]for p in vertices)],
            'physical_inventory_source':contract['physical_inventory_source'],'evidence':proof}}
    return result


def project_bound_intersection_ways(fields, highways):
    """Use complete validated native-road identities, never containment."""
    for value in fields.values():
        roads=value.get('_source_road_ids',[])
        if 'intersection'not in value.get('_verified_structure_kinds',[])or not roads or not all(highways.get(r)for r in roads):continue
        ways=sorted({way for road in roads for way in highways[road]})
        if not set(value.get('ways',[]))<=set(ways):raise ValueError('Intersection membership conflicts with verified native highways')
        value['ways']=ways


def retained_reference_crosswalk_fields(evidence, regions):
    """Bind an existing crosswalk to its original measured footway band.

    This consumes the original source geometry, not a new legal classification,
    paint claim, inferred width, or association with a nearby controller.
    """
    import json
    declaration=evidence.path('scenario_geometry.json')
    if declaration is None:return {}
    verification=json.loads(declaration.read_text()).get('physical_verification')
    if not isinstance(verification,dict):return {}
    name=verification.get('actual_original_reference_geometry')
    if name is not None and not isinstance(name,str):raise ValueError('Malformed original reference geometry path')
    if not name:return {}
    path=evidence.path(name)
    if path is None:raise ValueError('Declared original reference geometry is not integrity-bound')
    record=json.loads(path.read_text())
    if not isinstance(record,dict):raise ValueError('Malformed original reference geometry document')
    if record.get('kind')not in ('original_before_motion_reference_geometry','original_before_motion_line_first_geometry'):return {}
    if record.get('branch')=='no_line_marked_near_side_crosswalk':return {}
    native=record.get('crosswalk_band_native_xy_m')
    if native is None:return {}
    map_path=evidence.path('road.xodr')
    if map_path is None or record.get('source_map_sha256')!=evidence.used.get('road.xodr'):
        raise ValueError('Original crosswalk reference belongs to another source map')
    digest=record.get('source_helper_sha256')
    producers=[n[len('evidence/'):]for n,h in evidence.expected.items()
               if n.startswith('evidence/')and n.endswith('.py')and h==digest]
    if not producers or any(evidence.path(n)is None for n in producers):
        raise ValueError('Original crosswalk reference producer is not integrity-bound')
    endpoints=record.get('footway_endpoints')
    if not isinstance(endpoints,list)or len(endpoints)<2 or not record.get('topmost_survey'):
        raise ValueError('Original crosswalk reference lacks measured footway/surface support')
    for endpoint in endpoints:
        xyz=endpoint.get('native_xyz_m');width=endpoint.get('lane_width_m')
        if ('sidewalk'not in str(endpoint.get('lane_type','')).lower()or not isinstance(xyz,list)or len(xyz)!=3
                or any(type(v)not in(int,float)or not math.isfinite(v)for v in xyz)
                or type(width)not in(int,float)or not math.isfinite(width)or width<=0):
            raise ValueError('Malformed original footway connection measurement')
    if not isinstance(native,list)or any(not isinstance(p,list)or len(p)!=2 or
            any(type(v)not in(int,float)or not math.isfinite(v)for v in p)for p in native):
        raise ValueError('Malformed original crosswalk band')
    from shapely.geometry import Polygon
    boundary=normalized_polygon([[x,-y]for x,y in native]);shape=Polygon(boundary)
    matches=[]
    for region in regions:
        if region['kind']!='crosswalk'or region.get('boundary')is None:continue
        try:current=Polygon(normalized_polygon(region['boundary']))
        except (TypeError,ValueError):continue
        if current.equals(shape):matches.append(region['id'])
    if len(matches)>1:raise ValueError('Ambiguous retained original crosswalk identity')
    if not matches:return {}
    return {matches[0]:{'_crosswalk_geometry_source':{'method':'retained_original_footway_connection_band',
        'map_sha256':record['source_map_sha256'],'reference':name,'reference_sha256':evidence.used[name],
        'producer_sha256':digest,'source_kind':record['kind']},'_verified_structure_kinds':['crosswalk']}}


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
    from .roadways import apply_replacements, protected_regions
    junction_bindings=(inventory or {}).get('junction_bindings',[])
    junction_components={(source['junction_id'],source['component']):r['id'] for r in native
                         if (source:=region_sources.get(r['id'],{})).get('junction_id') is not None}
    junction_replacements=canonical_junctions(first.get('structures',[]),native,region_sources,
        junction_bindings,evidence.used.get('road.xodr'),protected_regions(first))
    if junction_replacements:
        first=apply_replacements(first,junction_replacements,tuple(junction_replacements))
    base_remap=match_regions(native,first.get('structures',[]))
    existing={r['id']:r for r in first.get('structures',[])}
    for region in native:
        if region['kind']!='highway' and not region.get('boundary') and region['id'] in existing and existing[region['id']]['kind']==region['kind']:
            base_remap[region['id']]=region['id']
    from .roadways import merge_highways
    highway_methods={}
    merged,group_issues=merge_highways(path,native,polygons,provenance,(declaration or {}).get('way_groups',[]),highway_methods)
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
    replacements=dict(junction_replacements)
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
    partition_lanes={}
    partition_roads=partition_source_roads(native,first.get('structures',[]),region_sources,provenance,lane_sources=partition_lanes)
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
    fields=bound_junction_source_fields(junction_components,provenance,junction_bindings,junction_replacements)
    for ident,value in reviewed_intersection_source_fields(evidence,first.get('structures',[]),
            native,region_sources,provenance,evidence.used.get('road.xodr')).items():
        if ident in fields and any(k in fields[ident] and fields[ident][k]!=v for k,v in value.items()):
            raise ValueError('Conflicting reviewed intersection source identity')
        fields.setdefault(ident,{}).update(value)
    from collections import Counter
    native_target_counts=Counter(remap[r['id']] for r in native if r['id'] in remap)
    for r in native:
        if r['id'] not in remap:continue
        target=remap[r['id']];value={}
        # Preserve source-computed whole-roadway scalars only for one exact
        # native identity. Variable profiles never become local-frame defaults.
        if r['kind']=='roadway' and native_target_counts[target]==1:
            for key in ('curvature','grade'):
                if key in r:value[key]=r[key]
        if r['kind']=='highway':
            if r['id'] in highway_methods:value['_highway_geometry_source']=highway_methods[r['id']]
            surface_methods=[v for v in region_sources.values()if 'highway_geometry_method'in v and v['road_id']in provenance.get(r['id'],[])]
            if surface_methods:
                value.setdefault('_highway_geometry_source',{'method':'native_source_surface','source_roads':provenance.get(r['id'],[])})['source_surfaces']=surface_methods
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
        if r['kind'] in ('shoulder','sidewalk','median_or_divider','bicycle_lane_or_path') and roads and native_target_counts[target]==1:
            native_source=region_sources.get(r['id'],{})
            if {'road_id','section','lane_id'}<=native_source.keys() and set(roads)=={native_source['road_id']}:
                value['_source_road_ids']=sorted(set(roads))
        if r['kind']!='highway' and roads and all(road in highways for road in roads):
            value['ways']=sorted({i for road in roads for i in highways[road]})
        value['_verified_structure_kinds']=[r['kind']]
        if value:fields.setdefault(target,{}).update(value)
    for ident,roads in partition_roads.items():
        if roads and all(road in highways for road in roads):fields.setdefault(ident,{})['ways']=sorted({way for road in roads for way in highways[road]})
        if ident in partition_lanes and not fields.get(ident,{}).get('_lane_source'):
            value=fields.setdefault(ident,{})
            value['_lane_source']=partition_lanes[ident]
            value['_verified_structure_kinds']=['lane']
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
                fields.setdefault(r['id'],{})['_verified_structure_kinds']=['roadway']
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
    for ident,value in retained_reference_crosswalk_fields(evidence,first.get('structures',[])).items():
        fields.setdefault(ident,{}).update(value)
    for ident,value in entrance_geometry_fields(path,first.get('structures',[]),
            (inventory or {}).get('painted_stop_line_bindings',[])).items():
        fields.setdefault(ident,{}).update(value)
    report_names=['traffic_spec/adapter_report.json']+[name[len('evidence/'):]for name in sorted(evidence.expected)
        if name.startswith('evidence/traffic_spec/report_history/adapter_report-')and name.endswith('.json')]
    centre_fields={}
    for name in report_names:
        source_report=evidence.path(name)
        if source_report is None:continue
        projected=retained_centre_line_fields(path,first.get('structures',[]),
            json.loads(source_report.read_text()),evidence.used.get('road.xodr'))
        for ident,value in projected.items():
            if ident in centre_fields and centre_fields[ident]!=value:
                raise ValueError('Conflicting retained centre-line source reports: '+str(ident))
            centre_fields[ident]=value
    for ident,value in centre_fields.items():fields.setdefault(ident,{}).update(value)
    from .control_portions import retained_authored_portion_fields
    for ident,value in retained_authored_portion_fields(evidence,first.get('structures',[]),highways).items():
        current=fields.setdefault(ident,{})
        for key,item in value.items():
            if key=='_verified_structure_kinds':
                current[key]=sorted(set(current.get(key,[]))|set(item))
            elif key in current and current[key]!=item:
                raise ValueError('Conflicting authored control-portion source field: '+key)
            else:current[key]=item
    for ident,value in retained_obstruction_fields(evidence,first,inventory).items():fields.setdefault(ident,{}).update(value)
    project_bound_intersection_ways(fields,highways)
    for retired,keep in junction_replacements.items():
        fields.setdefault(keep,{}).setdefault('_junction_property_merges',[]).append(retired)
    notes=[x['unknown_geometry'] for x in issues if 'unknown_geometry' in x]
    return fields,native_lanes,additions,replacements,notes+group_issues


def retained_centre_line_fields(path, regions, report, map_sha256):
    """Repair source-bound line-like boundaries without changing region identity."""
    from shapely.geometry import LineString, Point, Polygon
    records=report.get('native_centre_lines',[])
    if not records:return {}
    if report.get('inputs',{}).get('map',{}).get('sha256')!=map_sha256:
        raise ValueError('Centre-line source report belongs to another map')
    native={(o['source']['road_id'],o['source']['section_id']):o for o in native_centre_lines(path)}
    existing={r['id']:r for r in regions};fields={};seen=set()
    for record in records:
        ident=record['region_id'];key=(record['road_id'],record['section_id'])
        if ident in fields or key in seen:raise ValueError('Duplicated centre-line source identity')
        seen.add(key)
        region=existing.get(ident);observation=native.get(key)
        if region is None or region.get('kind')!='centre_line' or observation is None:
            raise ValueError('Centre-line source identity has no retained region')
        boundary=region.get('boundary');reference=record.get('native_centerline')
        if not boundary:
            raise ValueError('Centre-line source geometry unavailable for region '+str(ident))
        line_only=record.get('method')=='Native opposing driving-lane divider; directed increasing source s; <=2m sampling'
        declared_estimate=record.get('method')=='estimated_centreline_buffer_1cm'
        estimate_contract=record.get('geometry_method',{})
        if declared_estimate:
            expected=observation['source']['geometry_method']
            if not isinstance(estimate_contract,dict) or any(estimate_contract.get(k)!=expected[k] for k in
                    ('total_width_m','half_width_m','caps','joins','coordinate_quantization_m')):
                raise ValueError('Centre-line estimated strip contract conflicts with native map: '+str(ident))
        if line_only or declared_estimate:
            references=([reference] if reference else [])+([estimate_contract.get('reference_points')] if declared_estimate else [])
            for reference_points in references:
                # Historical chords may use 2 m samples. Check their vertices
                # against the native analytic sampling bound, not chord Hausdorff.
                native_reference=LineString(observation['source']['native_centerline'])
                declared_reference=LineString(reference_points)
                error=observation['source']['geometry_method']['max_reference_deviation_m']+1e-6
                if (declared_reference.length<=0 or not declared_reference.is_simple
                        or any(native_reference.distance(Point(point))>error for point in reference_points)
                        or math.dist(reference_points[0],observation['source']['native_centerline'][0])>1e-6
                        or math.dist(reference_points[-1],observation['source']['native_centerline'][-1])>1e-6):
                    raise ValueError('Centre-line source reference conflicts with native map: '+str(ident))
        estimated=False
        try:
            normalized=normalized_polygon(boundary)
        except ValueError:
            normalized=None
        if normalized is not None and (line_only or declared_estimate):
            if Polygon(normalized).equals(observation['shape']):
                normalized=observation['region']['boundary']
                estimated=True
            else:
                normalized=None
        if normalized is None:
            original=LineString(reference or observation['source']['native_centerline'])
            retained=LineString(boundary)
            matches=(original.hausdorff_distance(retained)<=1e-6 if reference else
                     all(original.distance(Point(point))<=STRIP_SAMPLING_ERROR_M+1e-6 for point in boundary))
            if original.length<=0 or not original.is_simple or not matches:
                raise ValueError('Retained centre-line differs from its source reference: '+str(ident))
            normalized=observation['region']['boundary']
            estimated=True
        source=dict(observation['source'])
        if not estimated:
            source['method']='retained_valid_area_outline'
            source.pop('geometry_method',None)
            source['scope']='Retained area geometry; this projection does not independently establish physical paint or measured width'
        fields[ident]={'boundary':normalized,'_centre_line_source':source,'_verified_structure_kinds':['centre_line']}
    return fields


def entrance_geometry_fields(path, regions, verified_stop_lines=()):
    """Join source gate geometry; preserve measured areas before estimated strips."""
    fields={}
    observations=painted_map_objects(path,verified_stop_lines)
    for observation in observations:
        native_region=observation['region']
        if native_region['kind']=='crosswalk':
            from .roadways import boundary_key
            def area_key(boundary):
                try:boundary=normalized_polygon(boundary)
                except (ValueError,TypeError):return None
                return boundary_key(boundary)
            expected=area_key(native_region.get('boundary'))
            matches=[r for r in regions if r['kind']=='crosswalk'and expected is not None
                     and area_key(r.get('boundary'))==expected]
            if len(matches)>1:raise ValueError('Ambiguous retained native crosswalk area')
            if matches:fields.setdefault(matches[0]['id'],{}).update(
                _crosswalk_geometry_source=dict(observation['source'],method='exact_native_crosswalk_area'),
                _verified_structure_kinds=['crosswalk'])
            continue
        if native_region['kind']!='stop_line':continue
        source=observation['source']
        if source.get('representation')=='polygon':
            # A validated physical paint/reference binding joins an explicit
            # source area; it does not authorize an estimated width or a new outline.
            verified={(b['road_id'],b['object_id']):b for b in verified_stop_lines}
            binding=verified.get((source['road_id'],source['object_id']))
            if binding is None:continue
            from .roadways import boundary_key
            def area_key(boundary):
                try:normalized_polygon(boundary)
                except (ValueError,TypeError):return None
                return boundary_key([[round(v,6) for v in p] for p in boundary])
            expected=area_key(native_region.get('boundary'))
            coincident=[o for o in observations if o['region']['kind']=='stop_line'
                        and expected is not None and area_key(o['region'].get('boundary'))==expected]
            if len(coincident)!=1:raise ValueError('Verified source stop-line area has ambiguous native identity')
            matches=[r for r in regions if r['kind']=='stop_line' and expected is not None
                     and area_key(r.get('boundary'))==expected]
            if len(matches)>1:raise ValueError('Verified source stop-line area has ambiguous retained identity')
            if matches:
                fields.setdefault(matches[0]['id'],{}).update(
                    _stop_line_geometry_source=dict(source,paint_verification=binding,
                        geometry_method='retained_source_area_outline'),
                    _verified_structure_kinds=['stop_line'])
            continue
        if 'native_centerline' not in source:continue
        matches=[r for r in regions if r['kind']=='stop_line' and r.get('position')
                 and math.dist(r['position'],native_region['position'])<=1e-5]
        if len(matches)==1:
            coincident=[o for o in observations if o['region']['kind']=='stop_line'
                and math.dist(o['region']['position'],native_region['position'])<=1e-5]
            if len(coincident)!=1:
                if source.get('geometry_method')=='estimated_verified_stop_line_strip_35cm':
                    raise ValueError('Verified painted stop line has ambiguous retained native identity')
                continue
            value=fields.setdefault(matches[0]['id'],{})
            boundary=matches[0].get('boundary');valid_area=False
            if boundary is not None:
                try:normalized_polygon(boundary);valid_area=True
                except ValueError:pass
            if not valid_area:
                if source.get('geometry_method')=='estimated_verified_stop_line_strip_35cm':
                    value['boundary']=native_region['boundary']
                    value['_stop_line_geometry_source']=source
                elif boundary is not None:
                    value['_unobserved_paint_boundary']=True
            if source.get('geometry_method')=='estimated_verified_stop_line_strip_35cm':
                value['_verified_structure_kinds']=['stop_line']
            value['_entrance_geometry']=source['native_centerline']
            value['_entrance_road']=source['road_id']
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
        variable_markings=bool(source and any(len({repr(v) for a,b,v in spans})>1
            for spans in source.get('marking_intervals',{}).values()))
        if original['kind']!='lane' or not source or (lane.get('direction') is not None and not variable_markings):continue
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
            if len(boundary)<3:break
            shape=Polygon(boundary)
            if not shape.is_valid or shape.area<=1e-8:break
            vector=[sum(b[k][j]-a[k][j] for k in (1,2))/2 for j in (0,1)]
            norm=math.hypot(*vector)
            if norm<=1e-9:break
            direction=[v/norm*(-1 if source['lane_id']>0 else 1) for v in vector]
            value=copy.deepcopy(original);value['boundary']=boundary
            value['lane']=dict(copy.deepcopy(lane),direction=direction)
            for side,spans in source.get('marking_intervals',{}).items():
                midpoint=(a[0]+b[0])/2
                matches=[v for low,high,v in spans if low<=midpoint<high]
                value['lane'].pop('marking_'+side,None)
                if len(matches)==1 and matches[0] is not None:
                    value['lane']['marking_'+side]=copy.deepcopy(matches[0])
            value['id']=ident if not pieces else next_id
            if pieces:next_id+=1
            pieces.append((value,(a[0],b[0])))
        if len(pieces)!=len(pairs) or not pieces:
            issues.append('Lane '+str(ident)+' has a degenerate native segment; full footprint retained without subdivision')
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
    shapes={p['id']:Polygon(p['boundary']) for pieces in segments.values() for p,_ in pieces}
    fields=fields or {}
    entrances={ident:LineString(v['_entrance_geometry']) for ident,v in fields.items() if v.get('_entrance_geometry')}
    sources={ident:v['_lane_source']['road_id'] for ident,v in fields.items() if v.get('_lane_source')}
    connections={ident:{sources[target] for target in v.get('lane',{}).get('leads_to',[]) if target in sources}
                 for ident,v in fields.items() if v.get('lane')}
    native_shapes={}
    for ident,field in fields.items():
        samples=field.get('_lane_source',{}).get('samples',[])
        if len(samples)>1:
            polygon=Polygon([a for station,a,b in samples]+[b for station,a,b in reversed(samples)])
            if polygon.is_valid and polygon.area>0:native_shapes[ident]=polygon
    continuations={ident:[native_shapes[target] for target in field.get('lane',{}).get('leads_to',[])
        if target in native_shapes]for ident,field in fields.items()}
    for ident,field in fields.items():
        for native in field.get('_lane_source',{}).get('native_continuations',[]):
            samples=native['samples']
            polygon=Polygon([a for station,a,b in samples]+[b for station,a,b in reversed(samples)])
            if polygon.is_valid and polygon.area>0:continuations.setdefault(ident,[]).append(polygon)
    return {'shapes':shapes,
        'entrances':entrances,'entrance_roads':{ident:v['_entrance_road'] for ident,v in fields.items() if '_entrance_road' in v},
        'connections':connections,'continuations':continuations}


def project_lane_segments(scene, segments, compiled=None):
    """Relink a static lane partition; final producer owns all occupancy."""
    import copy
    from shapely.geometry import Polygon,Point
    if not segments:return 0
    if any(i['target'] in segments for i in scene.get('intents',[])):
        raise ValueError('Scoped lane intention needs an explicit segment target')
    compiled=compiled if compiled is not None else compile_lane_segments(segments)
    shapes=compiled['shapes'];entrances=compiled['entrances']
    original={r['id']:r for r in scene['structures']}
    # Partition templates predate per-frame inventory and membership projection.
    # Preserve those current classifications; replace only partition geometry/IDs
    # and the lane fields whose references/direction depend on the subdivision.
    scene['structures']=[p for r in scene['structures'] for p in
        ([dict(copy.deepcopy({k:v for k,v in r.items() if k not in ('id','boundary','lane')}),
               id=p['id'],boundary=copy.deepcopy(p['boundary']),
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
                # The original gate join also permits an immediate mapped junction
                # continuation. Retain that same proof when the incoming lane splits.
                for target in targets:
                    if target not in segments or any(p['id'] in associated for p,_ in segments[target]):continue
                    continuations=compiled.get('continuations',{}).get(target,[])
                    matches=any(part.intersection(shape).area>1e-4 if region['kind']=='crosswalk'
                        else part.distance(shape)<=0.15 for part in continuations)
                    if matches:associated.append(segments[target][-1][0]['id'])
                region['entrance_of']=list(dict.fromkeys(associated))
                if not region['entrance_of']:raise ValueError('Measured entrance does not meet any lane segment: '+repr({'region':region,'targets':targets,'source_road':compiled['entrance_roads'].get(region['id']),'connections':{t:list(compiled['connections'].get(t,set()))for t in targets},'distances':[(i,shapes[i].distance(shape))for i in expanded(targets)if i in shapes]}))
    for device in scene.get('devices',[]):
        if device.get('governs') is not None:device['governs']=expanded(device['governs'])
    scene['occupancy_observed']=[]
    scene['occupies']=[pair for pair in scene.get('occupies',[]) if pair[1] not in segments]
    return sum(len(pieces) for pieces in segments.values())
