"""Map explicitly authored speed-control portions onto recorded native geometry.

Native trigger-lane association does not establish a longitudinal legal zone.
Use only the retained synthetic zone declaration, preserve its provenance, and
keep original graph edges in supplementary evidence.
"""
import json,math,xml.etree.ElementTree as ET
from pathlib import Path
from .geometry import polynomial,reference,xy


def lane_portion(path,road_id,section_id,lane_id,interval):
    from shapely.geometry import Polygon
    road=next(r for r in ET.parse(path).getroot().findall('road') if int(r.attrib['id'])==road_id)
    sections=road.findall('./lanes/laneSection');section=sections[section_id]
    start=float(section.attrib['s']);end=float(sections[section_id+1].attrib['s']) if section_id+1<len(sections) else float(road.attrib['length'])
    a,b=interval
    if not start<=a<b<=end:raise ValueError('Authored portion extends outside native lane section')
    lanes=section.findall('./left/lane')+section.findall('./right/lane')
    lane=next(l for l in lanes if int(l.attrib['id'])==lane_id)
    if lane.attrib['type']!='driving':raise ValueError('Authored speed portion is not a native driving lane')
    geoms=road.findall('./planView/geometry')
    def edge(station,outer):
        g=next(g for g in reversed(geoms) if float(g.attrib['s'])<=station+1e-9)
        x,y,h,_=reference(g,station);offset=polynomial(road.findall('./lanes/laneOffset'),station);sign=1 if lane_id>0 else -1
        for l in sorted((l for l in lanes if int(l.attrib['id'])*sign>0),key=lambda l:abs(int(l.attrib['id']))):
            lid=int(l.attrib['id'])
            if abs(lid)<abs(lane_id) or lid==lane_id and outer:offset+=sign*polynomial(l.findall('width'),station-start,'sOffset')
        return [x-math.sin(h)*offset,y+math.cos(h)*offset]
    stations=sorted(set([a,b]+[a+i*2 for i in range(1,math.ceil((b-a)/2))]+[float(g.attrib['s']) for g in geoms if a<float(g.attrib['s'])<b]))
    boundary=[edge(s,False) for s in stations]+[edge(s,True) for s in reversed(stations)]
    polygon=Polygon(boundary)
    if not polygon.is_valid or polygon.area<=0:raise ValueError('Invalid authored speed-control portion')
    return boundary,polygon,end


def apply(original,regions,polygons,lane_ids,devices):
    config_path=Path(original)/'config.json'
    if not config_path.exists():return []
    config=json.loads(config_path.read_text())
    if config.get('unsigned_context') or config.get('posting',{}).get('authority_status')!='authored_synthetic_fact':return []
    zone=config.get('zone',{})
    if not all(k in zone for k in ('road_id','section_id','lane_id','station_interval_m','end_sign')):raise ValueError('Authored posting lacks recorded longitudinal zone')
    key=tuple(zone[k] for k in ('road_id','section_id','lane_id'))
    if key not in lane_ids:raise ValueError('Authored posting lane missing from native map')
    a,b=zone['station_interval_m'];boundary,polygon,end=lane_portion(Path(original)/'road.xodr',*key,[a,b])
    tolerance=config['measurements']['sign_position_tolerance_m'];mapping=[]
    for sign,interval in ((config['sign'],[a,b]),(zone['end_sign'],[b,end])):
        target=xy(sign['position_m']);speed=float(sign['type'].rsplit('.',1)[1])/3.6
        matches=[(k,d) for k,d in devices.items() if k[0]=='actor' and d['kind']=='speed_limit_sign' and d.get('position') and math.dist(d['position'],target)<=tolerance and abs(d.get('speed_value',-1)-speed)<1e-6 and lane_ids[key] in d.get('governs',[])]
        if len(matches)!=1:raise ValueError('Authored posting lacks exactly one observed native speed-limit actor/trigger lane')
        device_key,device=matches[0];boundary,polygon,_=lane_portion(Path(original)/'road.xodr',*key,interval)
        ident=len(regions)+1
        regions.append({'id':ident,'kind':'roadway','boundary':boundary});polygons[ident]=polygon
        native_governs=device['governs'];device['governs']=[ident]
        mapping.append({'device_key':list(device_key),'governed_region':ident,'native_trigger_lane_region':native_governs,'native_lane':list(key),'station_interval_m':interval,'speed_mps':speed,'scope':'authored_synthetic_spatial_applicability','source_config':str(config_path),'source_map':str(Path(original)/'road.xodr'),'provenance':zone.get('provenance'),'method':'Recorded explicit authored bounds sampled on original native driving-lane geometry; original graph association retained in supplementary evidence. This is not a legal governance inference.'})
    return mapping


def retained_authored_portion_fields(evidence,regions,highways):
    config_path=evidence.path("config.json")
    if config_path is None:return {}
    config=json.loads(config_path.read_text())
    if config.get("unsigned_context") or config.get("posting",{}).get("authority_status")!="authored_synthetic_fact":return {}
    zone=config.get("zone",{})
    if zone.get("end_sign") is not None or zone.get("end_boundary_kind")!="road_end" or not config["posting"].get("single_native_sign_road_end"):return {}
    if not isinstance(zone.get("provenance"),str)or not zone["provenance"]:raise ValueError("Authored road-end portion lacks explicit provenance")
    identity_path=evidence.path("actual_scene_identity.json");map_path=evidence.path("road.xodr");capture_path=evidence.path("capture/manifest.json")
    if None in (identity_path,map_path,capture_path):raise ValueError("Authored road-end portion source identity unavailable")
    identity=json.loads(identity_path.read_text());capture=json.loads(capture_path.read_text())
    if config.get("case_id")!=capture.get("case_id")or identity.get("Native_map_sha256")!=evidence.used["road.xodr"]:raise ValueError("Authored road-end portion source binding conflict")
    observed=identity.get("synthetic_context",{}).get("scene_assumptions",{}).get("governed_portion",{})
    keys=("road_id","section_id","lane_id","station_interval_m")
    if any(zone.get(k)!=observed.get(k)for k in keys):raise ValueError("Authored road-end portion differs from original scene declaration")
    if type(identity.get("sign_actor_id")) is not int or identity.get("landmark_id")!=config.get("sign",{}).get("landmark_id"):raise ValueError("Authored road-end portion sign identity conflict")
    road,section,lane=(zone[k]for k in keys[:3]);interval=zone["station_interval_m"]
    if any(type(x)is not int for x in (road,section,lane)):raise ValueError("Authored portion native identity invalid")
    boundary,polygon,end=lane_portion(map_path,road,section,lane,interval)
    if interval[1]!=end:raise ValueError("Authored road-end portion does not end at source road end")
    # Exact whole source-native polygon and explicit retained roadway role;
    # no nearest, containment, lane-role cast, or governance inference.
    expected=[[round(v,6)for v in p]for p in boundary]
    matches=[r for r in regions if r.get("kind")=="roadway"and r.get("boundary")==expected]
    if len(matches)>1:raise ValueError("Authored road-end portion retained identity ambiguous")
    if not matches:return {}
    if road not in highways:raise ValueError("Authored road-end portion has no verified public-way source")
    from .roadways import roadway_intervals
    native_road=ET.parse(map_path).getroot().find("./road[@id='%s']"%road)
    intervals=roadway_intervals(native_road,native_road.findall('./planView/geometry'),*interval)
    value={"ways":list(highways[road]),"_source_road_ids":[road],"_verified_structure_kinds":["roadway"]}
    if intervals and intervals[0][0]==interval[0]and intervals[-1][1]==interval[1]and all(a[1]==b[0]for a,b in zip(intervals,intervals[1:])):
        for key in ('curvature','grade'):
            values={part[2][key]for part in intervals if key in part[2]}
            if len(values)==1 and all(key in part[2]for part in intervals):value[key]=values.pop()
    return {matches[0]["id"]:value}
