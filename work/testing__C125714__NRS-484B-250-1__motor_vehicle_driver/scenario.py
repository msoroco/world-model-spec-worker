"""One physical, uncontrolled crossing at a divided-road median opening.

This is a capability construction. The native junction and complete actor
footprints must be inspected after a future capture before delivery selection.
"""
import math
import xml.etree.ElementTree as ET


def _road(ident, x, y, heading, length, junction=-1, predecessor=None, successor=None):
    links = []
    for tag, value in [('predecessor', predecessor), ('successor', successor)]:
        if value:
            kind, other, contact = value
            attribute = '' if kind == 'junction' else ' contactPoint="%s"' % contact
            links.append('<%s elementType="%s" elementId="%s"%s/>' % (tag, kind, other, attribute))
    return ('<road name="crossing-%s" length="%s" id="%s" junction="%s">'
            '<link>%s</link><type s="0" type="rural"/><planView><geometry s="0" x="%s" y="%s" hdg="%s" length="%s"><line/></geometry></planView>'
            '<elevationProfile/><lateralProfile/><lanes><laneSection s="0"><center><lane id="0" type="none" level="false">'
            '<roadMark sOffset="0" type="solid" weight="standard" color="yellow" width=".12"/></lane></center>'
            '<right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link>'
            '<width sOffset="0" a="7" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="white" width=".12"/>'
            '</lane></right></laneSection></lanes></road>') % (ident, length, ident, junction, ''.join(links), x, y, heading, length)


def build_xodr():
    # Right-hand carriageway travels east at y=-3.5; opposing carriageway
    # travels west at y=23.5. The northbound crossing road intersects each.
    roads = [
        _road(1, 0, 0, 0, 190, successor=('junction', 10, '')),
        _road(2, 210, 0, 0, 390, predecessor=('junction', 10, '')),
        _road(11, 190, 0, 0, 20, 10, ('road', 1, 'end'), ('road', 2, 'start')),
        _road(3, 600, 20, math.pi, 390, successor=('junction', 20, '')),
        _road(4, 190, 20, math.pi, 190, predecessor=('junction', 20, '')),
        _road(21, 210, 20, math.pi, 20, 20, ('road', 3, 'end'), ('road', 4, 'start')),
        _road(5, 200, -200, math.pi/2, 193, successor=('junction', 10, '')),
        _road(6, 200, 0, math.pi/2, 20, predecessor=('junction', 10, ''), successor=('junction', 20, '')),
        _road(7, 200, 27, math.pi/2, 173, predecessor=('junction', 20, '')),
        _road(12, 200, -7, math.pi/2, 7, 10, ('road', 5, 'end'), ('road', 6, 'start')),
        _road(22, 200, 20, math.pi/2, 7, 20, ('road', 6, 'end'), ('road', 7, 'start'))]
    junctions = []
    for jid, connections in [(10, [(1, 11), (5, 12)]), (20, [(3, 21), (6, 22)])]:
        body = ''.join('<connection id="%s" incomingRoad="%s" connectingRoad="%s" contactPoint="start">'
                       '<laneLink from="-1" to="-1"/></connection>' % (i, incoming, connecting)
                       for i, (incoming, connecting) in enumerate(connections))
        junctions.append('<junction name="crossing-%s" id="%s">%s</junction>' % (jid, jid, body))
    return ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C125714-prior-entry" version="1" '
            'date="2026-10-27" north="400" south="-400" east="600" west="0"/>' +
            ''.join(roads) + ''.join(junctions) + '</OpenDRIVE>')


def static_check():
    root = ET.fromstring(build_xodr())
    ids = {int(r.attrib['id']) for r in root.findall('road')}
    assert {1, 2, 5, 6, 11, 12} <= ids
    assert len(root.findall('junction')) == 2
    assert not root.findall('.//signal')
    assert len({j.attrib['id'] for j in root.findall('junction')}) == 2
    return {'road_count': len(ids), 'junction_count': 2, 'official_control_count': 0}


def inside_crossing(vertices):
    # Conservative bracket; raw vertices are retained for exact saved analysis.
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    return min(xs) <= 207 and max(xs) >= 200 and min(ys) <= 0 and max(ys) >= -7


def route(role):
    if role == 'ego':
        return [(float(x), -3.5) for x in range(176, 261)]
    return [(203.5, float(y)) for y in range(-20, 61)]
