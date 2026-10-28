"""C104496 frozen straight crest and continuous three-point reversal geometry."""
import math,xml.etree.ElementTree as E
LENGTH=1500.;WIDTH=12.;CREST=750.;RADIUS=6.
def elevation(s):
 if s<650:return -4+.08*(s-650)
 if s>850:return -4-.08*(s-850)
 return -.0004*(s-750)**2
def xy(s,t=0):return (s,-t)
def xml():
 root=E.Element('OpenDRIVE');h=E.SubElement(root,'header',revMajor='1',revMinor='4',name='C104496 straight physical crest',version='1',north='20',south='-20',east='1500',west='0',vendor='scenario_pipeline');E.SubElement(h,'geoReference').text='+proj=tmerc +lat_0=0 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs'
 r=E.SubElement(root,'road',name='synthetic public highway crest',length=str(LENGTH),id='1',junction='-1');E.SubElement(r,'link');p=E.SubElement(r,'planView');g=E.SubElement(p,'geometry',s='0',x='0',y='0',hdg='0',length=str(LENGTH));E.SubElement(g,'line');e=E.SubElement(r,'elevationProfile')
 for s,a,b,c in [(0,elevation(0),.08,0),(650,-4,.08,-.0004),(850,-4,-.08,0)]:E.SubElement(e,'elevation',s=str(s),a=str(a),b=str(b),c=str(c),d='0')
 E.SubElement(r,'lateralProfile');lanes=E.SubElement(r,'lanes');E.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0');section=E.SubElement(lanes,'laneSection',s='0')
 for side,ident in [('left','1'),('center','0'),('right','-1')]:
  lane=E.SubElement(E.SubElement(section,side),'lane',id=ident,type='none' if ident=='0' else 'driving',level='false')
  if ident!='0':E.SubElement(lane,'link');E.SubElement(lane,'width',sOffset='0',a=str(WIDTH),b='0',c='0',d='0')
  E.SubElement(lane,'roadMark',sOffset='0',type='broken' if ident=='0' else 'solid',weight='standard',color='yellow' if ident=='0' else 'white',width='.12',laneChange='both')
 return E.tostring(root,encoding='unicode')+'\n'
def phases(station):
 p=[(station-8+i*.1,6.,0.) for i in range(81)];result=[{'name':'approach','gear':1,'points':p}];x,y,yaw=p[-1]
 for name,gear,stop in [('forward_left',1,-110),('reverse_right',-1,-145),('forward_left_exit',1,-180)]:
  angle=math.radians(stop);n=math.ceil(abs(angle-yaw)*RADIUS/.1);k=-1/RADIUS if gear==1 else 1/RADIUS;pts=[(x,y,yaw)]
  ox,oy,oa=x,y,yaw
  for i in range(1,n+1):
   a=oa+(angle-oa)*i/n;x=ox+(math.sin(a)-math.sin(oa))/k;y=oy-(math.cos(a)-math.cos(oa))/k;pts.append((x,y,a))
  yaw=angle;result.append({'name':name,'gear':gear,'points':pts})
 # Smooth same-heading transition into the opposite driving lane over 16m.
 pts=[];ox,oy=x,y
 for i in range(161):
  q=i/160.;xx=ox-16*q;yy=oy+(-6-oy)*(3*q*q-2*q*q*q);dy=(-6-oy)*(6*q-6*q*q)/16;pts.append((xx,yy,math.atan2(dy,-1)))
 result.append({'name':'opposite_lane_departure','gear':1,'points':pts});return result

def offline_check():
 from shapely.geometry import Polygon,box
 rows=[]
 for station in (700,725,750,775,800):
  clearance=1e9
  for phase in phases(station):
   points=phase['points'];assert len(points)>1
   for x,y,yaw in points:
    body=Polygon([(x+u*math.cos(yaw)-v*math.sin(yaw),y+u*math.sin(yaw)+v*math.cos(yaw)) for u,v in [(-2.6,-1.1),(2.6,-1.1),(2.6,1.1),(-2.6,1.1)]])
    support=box(400,-12,1100,12);assert support.covers(body),(station,phase['name'],x,y);clearance=min(clearance,body.distance(support.boundary))
  assert [p['gear'] for p in phases(station)]==[1,1,-1,1,1]
  rows.append({'station_m':station,'sampled_full_body_minimum_road_edge_clearance_m':clearance})
 return {'status':'passed_offline','no_simulator_connection':True,'geometry':'Straight 1500m two-way 24m-wide physical crest road; elevation maximum at750m; no curve substitution','full_body_envelope_m':[2.6,1.1],'requested_turn_radius_m':6,'native_steering_and_surface_support':'must be verified before driving','max_grade_ratio':.08,'incoming_visibility_routes':'Every selected trajectory station lies400..1100, leaving over230m in both lane approaches','variants':rows}
if __name__=='__main__':
 import json
 from pathlib import Path
 D=Path(__file__).resolve().parent;(D/'scene.xodr').write_text(xml());(D/'static-construction-checks.json').write_text(json.dumps(offline_check(),indent=2)+'\n');print(json.dumps(offline_check()))
