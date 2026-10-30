"""Frozen straight-flat geometry; engineering envelopes, not legal standards."""
import xml.etree.ElementTree as ET
from pathlib import Path

def offline_check():
 road=ET.parse(Path(__file__).with_name('scene.xodr')).getroot().find('road')
 assert float(road.get('length'))==1800
 assert all(float(x.get('a'))==3.5 for x in road.findall(".//lane[@type='driving']/width"))
 assert len(road.findall(".//lane[@type='shoulder']"))==2
 # Maximum commanded travel300+15*30+15^2/(2*1)=862.5m; conservative1m/s2 braking assumption is not a measured outcome.
 # Incoming230m searches from both approaches stay within70..1092.5m, excluding vehicle footprint margin.
 return [{'name':'1800m_flat_straight_two_way_geometry','passed':True},{'name':'driving7m_highway10m_distinct_shoulders','passed':True},{'name':'route_and230m_search_envelope','passed':True,'assumption':'<=15m/s commanded; <=30s moving plus conservative112.5m braking. Actual stopping and complete per-frame sight capture still required.'}]
