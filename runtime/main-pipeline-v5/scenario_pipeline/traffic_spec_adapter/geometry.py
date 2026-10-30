"""Observed body geometry and sampled OpenDRIVE regions, in TrafficSpec's frame.

Lane IDs identify full (road, section, lane) regions. Roadway patches are separate
regions so a curve's curvature is not assigned to adjoining straight sections.
Sampling is geometric approximation, never a legal interpretation. OpenDRIVE
is already right-handed; only CARLA observations need y/yaw reflection.
"""
import math
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


def static_map(path, junctions=False, junction_report=None, native_junction_boxes=(), include_non_driving=False, public_way_roads=()):
    """Build all source-map lanes and local roadway patches from line/arc geometry.

    Width/offset polynomials are evaluated at samples. Maximum sample spacing is
    2 m; polygons and occupancy are estimates. Unsupported geometry is an error,
    not an empty map. Variable lane direction/width/markings remain unasserted.
    """
    from shapely.geometry import Polygon
    regions, polygons, keys = [], {}, {}
    source = ET.parse(path).getroot()
    if any(type(ident)is not int for ident in public_way_roads):raise ValueError('Public-way road references must be native integer IDs')
    if set(public_way_roads)-{int(road.get('id'))for road in source.findall('road')}:raise ValueError('Declared public-way road ID absent from realized native map')
    for road in sorted(source.findall('road'), key=lambda r:int(r.attrib['id'])):
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
                    polygon=Polygon(boundary)
                    if not polygon.is_valid or polygon.area<=0:raise ValueError('Invalid full public-way native envelope')
                    ident=len(regions)+1;regions.append({'id':ident,'kind':'highway','boundary':boundary});polygons[ident]=polygon
            for lane in driving:
                lid=int(lane.attrib['id']); ident=len(regions)+1
                boundary=[edge(s,lid,False) for s in stations]+[edge(s,lid,True) for s in reversed(stations)]
                polygon=Polygon(boundary)
                if not polygon.is_valid: raise ValueError('Invalid lane polygon '+str((rid,section_index,lid)))
                same=sorted([int(l.attrib['id']) for l in driving if int(l.attrib['id'])*lid>0],key=abs)
                info={'ordinal':same.index(lid)+1,'count':len(same)}
                widths=lane.findall('width')
                if len(widths)==1 and all(float(widths[0].attrib.get(k,0))==0 for k in 'bcd'):
                    info['width']=float(widths[0].attrib['a'])
                # A winding lane has no single direction vector. Do not freeze
                # direction at the ego station and give it to all other actors.
                headings=[reference(next(g for g in reversed(geoms) if float(g.attrib['s'])<=s+1e-9),s)[2] for s in stations]
                if max(headings)-min(headings)<1e-8:
                    h=headings[0]+(math.pi if lid>0 else 0)
                    info['direction']=[math.cos(h),math.sin(h)]
                regions.append({'id':ident,'kind':'lane','boundary':boundary,'lane':info})
                polygons[ident]=polygon; keys[(rid,section_index,lid)]=ident
            if include_non_driving:
                # Native lane type is geometry provenance, not a legal district
                # or an invented sidewalk/shoulder inferred from a blank area.
                for lane in lanes:
                    kind={'sidewalk':'sidewalk','shoulder':'shoulder'}.get(lane.attrib.get('type'))
                    if not kind:continue
                    lid=int(lane.attrib['id'])
                    boundary=[edge(st,lid,False) for st in stations]+[edge(st,lid,True) for st in reversed(stations)]
                    polygon=Polygon(boundary)
                    if polygon.area<=1e-8:continue
                    if not polygon.is_valid:raise ValueError('Invalid native non-driving surface')
                    ident=len(regions)+1
                    regions.append({'id':ident,'kind':kind,'boundary':boundary})
                    polygons[ident]=polygon
            # These patches overlap full lane regions and carry constant local
            # reference curvature, in the source OpenDRIVE right-handed frame.
            for g in geoms:
                a=max(start,float(g.attrib['s'])); b=min(end,float(g.attrib['s'])+float(g.attrib['length']))
                if b<=a or not driving:continue
                pos=[int(l.attrib['id']) for l in driving if int(l.attrib['id'])>0]
                neg=[int(l.attrib['id']) for l in driving if int(l.attrib['id'])<0]
                sample=[a+i*(b-a)/max(1,math.ceil((b-a)/2)) for i in range(max(1,math.ceil((b-a)/2))+1)]
                left=max(pos) if pos else min(neg,key=abs); right=min(neg) if neg else min(pos,key=abs)
                boundary=[edge(s,left,bool(pos)) for s in sample]+[edge(s,right,bool(neg)) for s in reversed(sample)]
                ident=len(regions)+1; p=Polygon(boundary)
                if not p.is_valid:raise ValueError('Invalid roadway patch')
                region={'id':ident,'kind':'roadway','boundary':boundary,'curvature':reference(g,(a+b)/2)[3]}
                elevations=road.findall('./elevationProfile/elevation')
                active=[e for e in elevations if float(e.attrib['s'])<=a+1e-9]
                breaks=[e for e in elevations if a<float(e.attrib['s'])<b]
                if active and not breaks and all(float(active[-1].attrib.get(k,0))==0 for k in 'cd'):
                    region['grade']=float(active[-1].attrib.get('b',0))
                regions.append(region);polygons[ident]=p
    # Neighbours mean same-direction lanes only. Opposing lanes are not left/right neighbours.
    for key,ident in keys.items():
        rid,section,lid=key; info=next(r['lane'] for r in regions if r['id']==ident)
        sign=1 if lid>0 else -1
        if (rid,section,lid-sign) in keys: info['left']=keys[(rid,section,lid-sign)]
        if (rid,section,lid+sign) in keys: info['right']=keys[(rid,section,lid+sign)]
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
            observations.append({'region':{'kind':kind,'position':[x,y],'boundary':boundary},'shape':shape,
                'source':{'road_id':int(road.attrib['id']),'object_id':obj.attrib['id'],'object_attributes':dict(obj.attrib),
                          'representation':'polygon' if polygonal else 'zero-width native polyline; paint thickness unobserved'}})
    return observations
