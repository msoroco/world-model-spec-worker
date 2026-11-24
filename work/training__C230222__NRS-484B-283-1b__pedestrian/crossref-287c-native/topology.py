"""Connect both cross streets to the midblock through road in OpenDRIVE."""
import copy
import math
import xml.etree.ElementTree as ET


def _road(template, road_id, name, x, y, heading, length, junction):
    road = copy.deepcopy(template)
    road.attrib.update(id=str(road_id), name=name, length=str(length), junction=str(junction))
    geometry = road.find('planView/geometry')
    geometry.attrib.update(x=str(x), y=str(y), hdg=str(heading), length=str(length))
    road.find('link').clear()
    road.find('objects').clear()
    road.find('signals').clear()
    return road


def _link(road, direction, kind, ident, contact=None):
    attributes = {'elementType': kind, 'elementId': str(ident)}
    if contact is not None:
        attributes['contactPoint'] = contact
    ET.SubElement(road.find('link'), direction, attributes)


def _lane_links(road):
    for lane_id in ('-1', '1'):
        lane = road.find(".//lane[@id='" + lane_id + "']")
        links = ET.SubElement(lane, 'link')
        ET.SubElement(links, 'predecessor', {'id': lane_id})
        ET.SubElement(links, 'successor', {'id': lane_id})


def _connection(junction, number, incoming, connector, point, lane):
    connection = ET.SubElement(junction, 'connection', {
        'id': str(number), 'incomingRoad': str(incoming),
        'connectingRoad': str(connector), 'contactPoint': point})
    ET.SubElement(connection, 'laneLink', {'from': str(lane), 'to': str(lane)})


def road(original_xml, marked):
    root = ET.fromstring(original_xml)
    root.find('header').attrib.update(north='45', south='-45', east='25', west='-25')
    template = root.find('road')
    root.remove(template)
    roads = []
    def add(*args):
        item = _road(template, *args)
        roads.append(item)
        return item
    # Main road has a through connector at each adjacent cross-street junction.
    south = add(1, 'south_approach', 0, -40, 1.5707963267948966, 6.5, -1)
    first_through = add(8, 'south_junction_through', 0, -33.5, 1.5707963267948966, 7, 1)
    middle = add(9, 'midblock_curb_crossing', 0, -26.5, 1.5707963267948966, 53, -1)
    second_through = add(10, 'north_junction_through', 0, 26.5, 1.5707963267948966, 7, 2)
    north = add(11, 'north_departure', 0, 33.5, 1.5707963267948966, 6.5, -1)
    _link(south, 'successor', 'junction', 1)
    _link(first_through, 'predecessor', 'road', 1, 'end')
    _link(first_through, 'successor', 'road', 9, 'start')
    _link(middle, 'predecessor', 'junction', 1)
    _link(middle, 'successor', 'junction', 2)
    _link(second_through, 'predecessor', 'road', 9, 'end')
    _link(second_through, 'successor', 'road', 11, 'start')
    _link(north, 'predecessor', 'junction', 2)
    _lane_links(first_through)
    _lane_links(second_through)
    if marked:
        ET.SubElement(middle.find('objects'), 'object', {
            'id': '28703', 'name': 'midblock_marked_crosswalk_target',
            'type': 'crosswalk', 's': '26.5', 't': '0', 'zOffset': '0',
            'hdg': '-1.5707963267948966', 'length': '7', 'width': '3'})
    for item, role, signal_id, station in (
        (south, 'south', '28701', '6.0'),
        (middle, 'north', '28702', '52.5')):
        ET.SubElement(item.find('signals'), 'signal', {
            'id': signal_id, 'name': 'C230222_287c_' + role + '_device_target',
            's': station, 't': '-4', 'zOffset': '3.5', 'hOffset': '0',
            'pitch': '0', 'roll': '0', 'orientation': '+', 'dynamic': 'yes',
            'country': 'US', 'type': '1000001', 'subtype': '0',
            'value': '0', 'unit': '', 'height': '0.6', 'width': '0.3'})
    for number, y, west_id, connector_id, east_id in (
        (1, -30, 2, 3, 4), (2, 30, 5, 6, 7)):
        west = add(west_id, 'junction_' + str(number) + '_west', -20, y, 0, 16.5, -1)
        connector = add(connector_id, 'junction_' + str(number) + '_cross', -3.5, y, 0, 7, number)
        east = add(east_id, 'junction_' + str(number) + '_east', 3.5, y, 0, 16.5, -1)
        _link(west, 'successor', 'junction', number)
        _link(connector, 'predecessor', 'road', west_id, 'end')
        _link(connector, 'successor', 'road', east_id, 'start')
        _link(east, 'predecessor', 'junction', number)
        _lane_links(connector)
        junction = ET.SubElement(root, 'junction', {
            'id': str(number), 'name': 'adjacent_intersection_' + str(number)})
        through = 8 if number == 1 else 10
        south_id = 1 if number == 1 else 9
        north_id = 9 if number == 1 else 11
        for args in ((0, west_id, connector_id, 'start', '-1'),
                     (1, east_id, connector_id, 'end', '1'),
                     (2, south_id, through, 'start', '-1'),
                     (3, north_id, through, 'end', '1')):
            _connection(junction, *args)
    for item in sorted(roads, key=lambda value: int(value.get('id'))):
        root.append(item)
    return ET.tostring(root, encoding='unicode') + '\n'


def inspect(content):
    root = ET.fromstring(content)
    roads = {int(item.get('id')): item for item in root.findall('road')}
    junctions = {int(item.get('id')): item for item in root.findall('junction')}
    if set(roads) != set(range(1, 12)) or set(junctions) != {1, 2}:
        raise ValueError('Connected adjacent-intersection road inventory differs')
    for number, incoming, connector, outgoing in ((1, 1, 8, 9), (2, 9, 10, 11)):
        junction = junctions[number]
        relations = {(int(item.get('incomingRoad')), int(item.get('connectingRoad')),
                      item.get('contactPoint')) for item in junction.findall('connection')}
        if (len(relations) != 4 or (incoming, connector, 'start') not in relations or
                (outgoing, connector, 'end') not in relations):
            raise ValueError('Main road is disconnected from adjacent junction')
        if roads[connector].get('junction') != str(number):
            raise ValueError('Main through connector belongs to wrong junction')
    for incoming, connector, outgoing in ((1, 8, 9), (9, 10, 11),
                                          (2, 3, 4), (5, 6, 7)):
        a, b, c = (roads[ident] for ident in (incoming, connector, outgoing))
        successor = a.find('link/successor')
        predecessor = c.find('link/predecessor')
        if successor is None or predecessor is None or successor.get('elementType') != 'junction' or predecessor.get('elementType') != 'junction':
            raise ValueError('Approach road lacks junction link')
        if successor.get('elementId') != b.get('junction') or predecessor.get('elementId') != b.get('junction'):
            raise ValueError('Approach road points to wrong junction')
        if b.find('link/predecessor').get('elementId') != str(incoming) or b.find('link/successor').get('elementId') != str(outgoing):
            raise ValueError('Connector road link differs')
        def endpoints(item):
            geometry = item.find('planView/geometry')
            x, y, heading, length = (float(geometry.get(key)) for key in ('x', 'y', 'hdg', 'length'))
            return (x, y), (x + length * math.cos(heading), y + length * math.sin(heading))
        a_start, a_end = endpoints(a)
        b_start, b_end = endpoints(b)
        c_start, c_end = endpoints(c)
        if math.dist(a_end, b_start) > .001 or math.dist(b_end, c_start) > .001:
            raise ValueError('Connector endpoints are disconnected')
        for lane_id in ('-1', '1'):
            lane = b.find(".//lane[@id='" + lane_id + "']")
            if lane is None or lane.find('link/predecessor').get('id') != lane_id or lane.find('link/successor').get('id') != lane_id:
                raise ValueError('Connector lane link differs')
    for junction in junctions.values():
        for connection in junction.findall('connection'):
            connector = roads[int(connection.get('connectingRoad'))]
            lane_link = connection.find('laneLink')
            if lane_link is None or lane_link.get('from') != lane_link.get('to') or lane_link.get('to') not in ('-1', '1'):
                raise ValueError('Junction lane connection differs')
            if connector.get('junction') != junction.get('id'):
                raise ValueError('Junction connection targets wrong connector')
    return {'roads': 11, 'junctions': 2, 'connections': 8,
            'through_road_connected': True, 'lane_links_checked': 8,
            'native_map_loaded': False}
