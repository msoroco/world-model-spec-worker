"""Four connected analytic quarter arcs keep each Native lane surface simple."""
import math
from pathlib import Path
root=Path(__file__).resolve().parent
length=22*math.pi/2
roads=[]
for i in range(4):
    rid=i+1;previous=(i-1)%4+1;following=(i+1)%4+1
    angle=i*math.pi/2;x=22*math.cos(angle);y=22*math.sin(angle)
    roads.append(f'''  <road name="C234827 rotary quarter {rid}" length="{length:.12f}" id="{rid}" junction="-1">
    <link><predecessor elementType="road" elementId="{previous}" contactPoint="end"/><successor elementType="road" elementId="{following}" contactPoint="start"/></link>
    <type s="0" type="town"><speed max="20" unit="mph"/></type>
    <planView><geometry s="0" x="{x:.12f}" y="{y:.12f}" hdg="{angle+math.pi/2:.12f}" length="{length:.12f}"><arc curvature="{1/22:.16f}"/></geometry></planView>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0">
      <left/>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
      <right>
        <lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" color="white" width="0.12"/></lane>
        <lane id="-2" type="driving" level="false"><link><predecessor id="-2"/><successor id="-2"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
      </right>
    </laneSection></lanes>
    <objects/><signals/>
  </road>''')
xml='<?xml version="1.0" standalone="yes"?>\n<OpenDRIVE>\n  <header revMajor="1" revMinor="4" name="C234827-LVMC-roundabout-four-arc-request" version="1.00" date="2026-11-24" north="32" south="-32" east="32" west="-32" vendor="worker"/>\n'+'\n'.join(roads)+'\n</OpenDRIVE>\n'
(root/'road_30s.xodr').write_text(xml)
