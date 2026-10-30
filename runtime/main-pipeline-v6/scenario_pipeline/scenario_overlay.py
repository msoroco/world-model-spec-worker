"""Frame-synchronized expected labels and native-direction review diagrams."""
import hashlib,json,math
from pathlib import Path
from expected_labels import first_scene,load
from speed_overlay import ass_filter


def stamp(t):
 t=max(0,t);cs=round(t*100);return '%d:%02d:%02d.%02d'%(cs//360000,(cs//6000)%60,(cs//100)%60,cs%100)


def write_overlay(path,attempt,mapping,width,height,top=0,fps=20):
 record_path=attempt/'expected_label.json'
 if not record_path.exists():return None
 record=load(record_path);trace=[json.loads(s) for s in (attempt/'trace.jsonl').read_text().splitlines()];byframe={r['frame']:r for r in trace}
 scene=first_scene(attempt/'traffic_spec/trace.json');lane=[s for s in scene['structures'] if s['kind']=='lane'];cell=record['case_id'].split('-')[0]
 events=[]
 def add(a,b,text,layer=1):events.append('Dialogue: %d,%s,%s,Default,,0,0,0,,%s'%(layer,stamp(a),stamp(b),text))
 label=record['expected_label'] or ('not assigned (judgment sweep)' if record['judgment_sweep'] else 'missing evidence - diagnostic')
 title='Expected label: '+label+' | '+record['target_law_id']
 if record.get('inconclusive_reasons'):
  names={'unresolved_judgment':'judgment standard unresolved','missing_observations':'required observations missing','uncertain_activation':'activation uncertain','unsupported_reference_check':'reference check unavailable'}
  title+=' | '+', '.join(names.get(r,r) for r in record['inconclusive_reasons'])
 if record.get('intention_matched') is False and not record['judgment_sweep']:title+=' | intended outcome not achieved'
 add(0,len(mapping)/fps,r'{\an7\pos(8,%d)\fs14\bord2}'%(84 if top>=145 else top+4)+title)
 context=record['scene_assumptions']
 context_text=''
 if context.get('district'):
  measured=record['evidence'].get('measured_api_continuous_distance_ft')
  context_text='Signal lead: '+('%.3f ft'%measured if measured is not None else 'unavailable')+' | min '+str(record['evidence'].get('minimum_signal_distance_ft'))+' ft'
  add(0,len(mapping)/fps,r'{\an7\pos(8,%d)\fs12\bord2}'%(76 if top>=145 else top+40)+'Declared district: '+context['district'].replace('_',' '))
 if context.get('fixed_non_swept_conditions'):context_text='Declared fixed test context; see evidence.json'
 if cell=='C245490' and context.get('fixed_non_swept_conditions'):context_text='Declared context: marked lanes; fixed signaling and safety'
 if context.get('stopping_reference'):context_text='Declared stopping reference; see recorded trace geometry and evidence'
 if context_text:add(0,len(mapping)/fps,r'{\an7\pos(8,%d)\fs12\bord2}'%(64 if top>=145 else top+24)+context_text)
 x0=width-218;y0=top+27
 def draw(cmd,color='FFFFFF',a=0,b=None):add(a,len(mapping)/fps if b is None else b,r'{\an7\pos(%d,%d)\1c&H%s&\bord0\p1}%s{\p0}'%(x0,y0,color,cmd),0)
 def arrow(x,y,dx,dy,color='FFFFFF'):
  endx=x+dx;endy=y+dy
  length=max(1,math.hypot(dx,dy));nx=-dy/length;ny=dx/length
  draw('m %d %d l %d %d %d %d %d %d'%(x+nx,y+ny,endx+nx,endy+ny,endx-nx,endy-ny,x-nx,y-ny),color);draw('m %d %d l %d %d %d %d'%(endx-dx*.25-dy*.2,endy-dy*.25+dx*.2,endx,endy,endx-dx*.25+dy*.2,endy-dy*.25-dx*.2),color)
 if cell in ('C245490','C329610'):
  draw('m 0 0 l 214 0 214 125 0 125 0 0','202020')
  if cell=='C245490':
   n=len(lane);add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs12}Same-direction lanes: %d'%(x0+4,y0+3,n))
   for i in range(n):
    y=30+i*24;draw('m 5 %d l 208 %d 208 %d 5 %d'%(y,y,y+1,y+1),'CCCCCC');arrow(65,y+12,70,0,'66FF66')
   add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs11}Trace arrows; white: ego lane position'%(x0+4,y0+106))
   for i,m in enumerate(mapping):
    p=byframe[m['carla_frame']]['position'];yy=30+(n-(-p['y']/3.5))*24
    draw('m 101 %d l 111 %d 111 %d 101 %d'%(yy-5,yy-5,yy+5,yy+5),'FFFFFF',i/fps,(i+1)/fps)
  else:
   draw('m 4 50 l 85 50 85 18 129 18 129 50 208 50 208 94 129 94 129 124 85 124 85 94 4 94 4 50','606060')
   draw('m 4 70 l 208 70 208 72 4 72 m 106 18 l 108 18 108 124 106 124','00FFFF')
   arrow(12,83,52,0,'66FF66');arrow(198,60,-52,0,'6666FF');arrow(118,121,0,-22,'66FF66');arrow(96,22,0,22,'6666FF')
   add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs11}Green: east/north; red: west/south'%(x0+2,y0+2))
   add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs10}Yellow: centerline; white: ego'%(x0+2,y0+110))
   for i,m in enumerate(mapping):
    p=byframe[m['carla_frame'] if 'carla_frame' in m else m.get('original_frame',m.get('frame'))]['position'] if any(k in m for k in ('carla_frame','original_frame','frame')) else trace[m['video_frame']]['position']
    if p['x']<-30:
     add(i/fps,(i+1)/fps,r'{\an7\pos(%d,%d)\fs11}Ego upstream: %.0f m'%(x0+4,y0+107,-14-p['x']));continue
    xx=107+max(-30,min(30,p['x']))*2.6;yy=71-max(-20,min(20,-p['y']))*2.1
    draw('m %d %d l %d %d %d %d %d %d'%(xx-5,yy-5,xx+5,yy-5,xx+5,yy+5,xx-5,yy+5),'FFFFFF',i/fps,(i+1)/fps)
 elif record['target_law_id']=='NRS-484B-307-6a' and (attempt/'governing_signal_indication.jsonl').exists():
  states={r['time_s']:r['value']['state'] for r in (json.loads(s) for s in (attempt/'governing_signal_indication.jsonl').read_text().splitlines())}
  for i,m in enumerate(mapping):
   add(i/fps,(i+1)/fps,r'{\an7\pos(8,%d)\fs14\bord2}'%(top+24)+'Governing light: '+states[m['time_s']])
 elif record['target_law_id']=='NRS-484B-600-1c' and load(attempt/'measured_review.json').get('speed_evaluation'):
  review=load(attempt/'measured_review.json');active=set(review['speed_evaluation']['applicable_frames'])
  for i,m in enumerate(mapping):
   frame=m.get('carla_frame',m.get('original_frame',m.get('frame')));message='Inside posted portion: 60 km/h' if frame in active else 'Before posted portion / outside applicability'
   add(i/fps,(i+1)/fps,r'{\an7\pos(8,%d)\fs14\bord2}'%(top+24)+message)
 geometry_path=attempt/'scenario_geometry.json'
 if geometry_path.exists():
  geometry=load(geometry_path);polygons=[]
  for road in geometry.get('directed_roadways',[]):polygons.append((road['polygon'],'606060'))
  for polygon in geometry.get('prohibited_median_polygons',[]):polygons.append((polygon,'4444CC'))
  for polygon in geometry.get('median_opening_polygons',[]):polygons.append((polygon,'449944'))
  if geometry.get('intersection_polygon'):polygons.append((geometry['intersection_polygon'],'996633'))
  pts=[p for polygon,_ in polygons for p in polygon]+[[r['position']['x'],r['position']['y']] for r in trace]
  if pts:
   xmin=min(p[0] for p in pts);xmax=max(p[0] for p in pts);ymin=min(p[1] for p in pts);ymax=max(p[1] for p in pts)
   scale=min(194/max(1,xmax-xmin),115/max(1,ymax-ymin))
   def screen(p):return (10+(p[0]-xmin)*scale,25+(p[1]-ymin)*scale)
   def polygon_command(vertices):
    points=[screen(p) for p in vertices]
    return 'm '+' l '.join('%d %d'%(x,y) for x,y in points+[points[0]])
   draw('m 0 0 l 214 0 214 155 0 155 0 0','202020')
   for polygon,color in polygons:draw(polygon_command(polygon),color)
   for road in geometry.get('directed_roadways',[]):
    center=[sum(p[k] for p in road['polygon'])/len(road['polygon']) for k in (0,1)];x,y=screen(center);d=road['direction_xy'];length=max(1e-9,math.hypot(*d));arrow(x-12*d[0]/length,y-12*d[1]/length,24*d[0]/length,24*d[1]/length,'66FF66')
   for sign in geometry.get('direction_sign_objects',[]):
    x,y=screen(sign['position_m']);draw('m %d %d l %d %d %d %d %d %d'%(x-3,y-3,x+3,y-3,x+3,y+3,x-3,y+3),'FFFFFF')
   add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs10}Recorded geometry; green: allowed direction'%(x0+3,y0+3))
   add(0,len(mapping)/fps,r'{\an7\pos(%d,%d)\fs10}White: ego/sign; amber: other vehicle'%(x0+3,y0+142))
   evidence_path=attempt/'scenario_rule_evidence.jsonl'
   rule_by_frame={r['frame']:r['value'] for r in (json.loads(s) for s in evidence_path.read_text().splitlines())} if evidence_path.exists() else {}
   for i,m in enumerate(mapping):
    frame=m['carla_frame'];r=byframe[frame];value=rule_by_frame.get(frame,{})
    if value.get('ego_body_xy'):draw(polygon_command(value['ego_body_xy']),'FFFFFF',i/fps,(i+1)/fps)
    for participant in value.get('participants',[]):draw(polygon_command(participant['body_xy']),'00CCFF',i/fps,(i+1)/fps)
    if geometry.get('inoperative_signal_actor_ids'):
     ids=set(geometry['inoperative_signal_actor_ids']);states=[str(d['state']) for d in value.get('devices',[]) if d['actor_id'] in ids]
     add(i/fps,(i+1)/fps,r'{\an7\pos(8,%d)\fs13\bord2}'%(64 if top>=145 else top+24)+'Observed signal heads: '+', '.join(states))
 header='[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,DejaVu Sans,14,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'%(width,height)
 path.write_text(header+'\n'.join(events)+'\n');return hashlib.sha256(path.read_bytes()).hexdigest()
