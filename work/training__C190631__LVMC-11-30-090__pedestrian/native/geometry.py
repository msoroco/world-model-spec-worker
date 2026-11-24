"""Authored elevated roadway, shoulder, adjacent sidewalk for C190631."""
import json
import xml.etree.ElementTree as ET


def geometry():
    return {'sidewalk_provided': True, 'adjacent': True,
            'sidewalk_xy_m': [[-40, -6], [40, -6], [40, -4], [-40, -4]],
            'roadway_xy_m': [[-40, -3.5], [40, -3.5], [40, 0], [-40, 0]],
            'overpass_deck_z_m': 8,
            'source_status': 'authored_requires_native_readback',
            'boundary_gap_m': .5}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C190631-elevated-sidewalk',
                  version='1', date='2026-11-23', north='20', south='-20', east='50', west='-50',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='overpass-roadway-sidewalk', length='100', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-50', y='0', hdg='0', length='100')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='8', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'shoulder', .5), (-3, 'sidewalk', 2)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='0.1')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    g = geometry()
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    ids = [int(l.attrib['id']) for l in lanes]
    kinds = [l.attrib['type'] for l in lanes]
    widths = [float(l.find('width').attrib['a']) for l in lanes]
    if road.attrib['length'] != '100' or ids != [-1, -2, -3] or kinds != ['driving', 'shoulder', 'sidewalk'] or widths != [3.5, .5, 2]:
        raise ValueError('authored roadway/sidewalk lane inventory differs')
    if float(road.find('elevationProfile/elevation').attrib['a']) != 8:
        raise ValueError('overpass elevation differs')
    if g['roadway_xy_m'][0][1] != -3.5 or g['sidewalk_xy_m'][0][1] != -6:
        raise ValueError('surface polygon inventory differs')
    return {'passed': True, 'road_length_m': 100, 'lane_ids': ids,
            'lane_types': kinds, 'lane_widths_m': widths,
            'overpass_deck_z_m': 8, 'boundary_gap_m': .5,
            'native_map_readback_observed': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
