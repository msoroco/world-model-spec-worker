"""Authored road draft and offline path geometry; not observed map data."""
import math

def build_road(length=600.,width=3.5):
 if length<=0 or width<=0:raise ValueError('Positive road dimensions required')
 lanes=''
 for lane in (-1,-2):
  lanes+=('<lane id="%d" type="driving" level="false"><link/><width sOffset="0" a="%s" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" weight="standard" color="white" width="0.12" laneChange="both"/></lane>'%(lane,width))
 return ('<?xml version="1.0"?><OpenDRIVE><header revMajor="1" revMinor="4" name="draft-two-lane" version="1" date="2026-10-27" north="0" south="0" east="0" west="0"/><road name="draft" length="%s" id="1" junction="-1"><link/><type s="0" type="rural"/><planView><geometry s="0" x="0" y="0" hdg="0" length="%s"><line/></geometry></planView><elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.12"/></lane></center><right>%s</right></laneSection></lanes></road></OpenDRIVE>'%(length,length,lanes))

def route(maneuver):
 approach=[(float(x),-1.75) for x in range(20,161,2)]
 if maneuver=='right_turn':return approach+[(160+15*math.sin(t),-1.75+15*(1-math.cos(t))) for t in [i*math.pi/100 for i in range(1,51)]]
 if maneuver=='u_turn':return approach+[(160+12*math.sin(t),-1.75+12*(1-math.cos(t))) for t in [i*math.pi/100 for i in range(1,101)]]
 return approach+[(float(x),-1.75) for x in range(162,401,2)]

def signed_entry_time(samples,boundary_x):
 for left,right in zip(samples,samples[1:]):
  if left[1]<boundary_x<=right[1]:return (left[0],right[0])
 return None

def signal_distance(samples):
 total=0.
 for a,b in zip(samples,samples[1:]):
  if not (a['indicator'] and b['indicator']):total=0.
  else:total+=math.hypot(b['x']-a['x'],b['y']-a['y'])
 return total
