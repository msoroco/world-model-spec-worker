"""Unselected C62507 controlled-access exit paving request."""
import math
import xml.etree.ElementTree as ET

from geometry import _road, HIGHWAY_EDGE_Y_M

RAMP_START = (-40 * (2.5 / 9), 0.0)
RAMP_END = (RAMP_START[0] + 40.0, -9.0)


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C62507 exit candidate only', version='1',
                  date='2026-11-26', north='20', south='-20',
                  east='120', west='-100', vendor='worker')
    _road(root, 1, 'controlled-access highway candidate',
          (-100, 0), 0, 220, 'motorway')
    _road(root, 2, 'frontage road candidate',
          (-100, -9), 0, 220, 'town')
    dx, dy = RAMP_END[0] - RAMP_START[0], RAMP_END[1] - RAMP_START[1]
    _road(root, 4, 'authored exit paving', RAMP_START,
          math.atan2(dy, dx), math.hypot(dx, dy), 'rural')
    return ET.tostring(root, encoding='unicode')


def check():
    roads = ET.fromstring(open_drive()).findall('road')
    if [road.get('id') for road in roads] != ['1', '2', '4']:
        raise ValueError('Highway/frontage/exit road identity differs')
    if [road.find('type').get('type') for road in roads] != [
            'motorway', 'town', 'rural']:
        raise ValueError('Controlled-access exit road types differ')
    if not RAMP_END[1] < HIGHWAY_EDGE_Y_M < RAMP_START[1]:
        raise ValueError('Exit paving does not cross highway edge')
    crossing_fraction = (HIGHWAY_EDGE_Y_M + 1 - RAMP_START[1]) / (
        RAMP_END[1] - RAMP_START[1])
    crossing_x = RAMP_START[0] + crossing_fraction * (
        RAMP_END[0] - RAMP_START[0])
    if abs(crossing_x) > 1e-9:
        raise ValueError('Indicated exit paving misses footprint crossing')
    return {'catalog_candidate_cell': 'C62507',
            'exit_paving_crosses_edge': True,
            'indicated_exit_footprint_crossing_x_m': crossing_x,
            'native_lane_connectivity_verified': False,
            'controlled_access_or_official_authority_verified': False,
            'catalog_actor_eligibility_reviewed': False}
