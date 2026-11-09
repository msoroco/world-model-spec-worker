"""Authored mountain-road geometry and engineering route checks, with no legal verdict."""
import math

FEET_500_M = 152.4


def centre(s, radius=115.0):
    """Plan-view circular bend with a mild symmetric crest, metres."""
    theta = s / radius
    return (radius * math.sin(theta), radius * (1 - math.cos(theta)),
            11.0 + 6.0 * math.exp(-((s - 190.0) / 90.0) ** 2))


def tangent(s, radius=115.0):
    theta = s / radius
    return (math.cos(theta), math.sin(theta))


def point(s, lateral=0.0):
    x, y, z = centre(s)
    tx, ty = tangent(s)
    return (x - lateral * ty, y + lateral * tx, z)


def route(turn_station=190.0, spacing=0.75):
    """A finite three-point reversal inside the widened bend turnout.

    Each tuple is x,y,z,forward flag. Reverse remains explicit; the controller
    must stop at direction changes. The body envelope is checked in Native.
    """
    if not 180 <= turn_station <= 200 or not 0.25 <= spacing <= 1.0:
        raise ValueError('Turn station or route spacing outside authored turnout')
    samples = []
    for i in range(int(30 / spacing) + 1):
        samples.append((*point(turn_station - 30 + i * 30 / int(30 / spacing), -3.0), True))
    # Forward left arc followed by a backing right-steer arc. With reverse
    # velocity the latter continues increasing heading toward 180 degrees.
    n = int(9 / spacing) + 1
    tx, ty = tangent(turn_station)
    bx, by, bz = point(turn_station, -3.0)
    for i in range(1, n + 1):
        a = (i / n) * math.radians(110)
        dx = 4.5 * math.sin(a)
        dy = 4.5 * (1 - math.cos(a))
        samples.append((bx + dx * tx - dy * ty, by + dx * ty + dy * tx, bz, True))
    # The backing phase creates turning room without teleporting the vehicle.
    ex, ey, ez, _ = samples[-1]
    n = int(5.5 / spacing) + 1
    start = math.radians(110)
    for i in range(1, n + 1):
        a = start + (i / n) * math.radians(70)
        dx = -4.5 * (math.sin(a) - math.sin(start))
        dy = 4.5 * (math.cos(a) - math.cos(start))
        samples.append((ex + dx * tx - dy * ty, ey + dx * ty + dy * tx, ez, False))
    rx, ry, rz, _ = samples[-1]
    n = int(28 / spacing) + 1
    for i in range(1, n + 1):
        d = 28 * i / n
        lateral = 3.0 * min(1.0, d / 10.0)
        samples.append((rx - d * tx - lateral * ty,
                        ry - d * ty + lateral * tx, rz, True))
    return samples


def validate_route(samples):
    if not samples or len(samples) < 20 or {p[3] for p in samples} != {True, False}:
        raise ValueError('Finite forward and reverse route required')
    for a, b in zip(samples, samples[1:]):
        gap = math.dist(a[:2], b[:2])
        if not 0 < gap < 1.5:
            raise ValueError('Discontinuous route')
    if math.dist(samples[0][:2], samples[-1][:2]) < 5:
        raise ValueError('No meaningful route displacement')
    return True


def xodr():
    """One continuous two-way curve with a crest and widened bend turnout."""
    return '''<?xml version="1.0" standalone="yes"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C129731_mountain_curve" version="1.00" date="2026-11-08" north="0" south="0" east="0" west="0"/>
<road name="mountain_curve" length="440" id="1" junction="-1">
<planView><geometry s="0" x="0" y="0" hdg="0" length="440"><arc curvature="0.008695652173913044"/></geometry></planView>
<elevationProfile><elevation s="0" a="11" b="0.015" c="0" d="0"/><elevation s="150" a="13.25" b="0.025" c="-0.00015" d="0"/><elevation s="250" a="14.25" b="-0.025" c="0" d="0"/></elevationProfile>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="broken" weight="standard" color="standard" width="0.15"/></lane></center>
<left><lane id="1" type="driving" level="false"><width sOffset="0" a="6" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="standard" width="0.15"/></lane></left>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="6" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" weight="standard" color="standard" width="0.15"/></lane></right></laneSection></lanes>
</road></OpenDRIVE>'''


def plan_check():
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xodr())
    road = root.find('road')
    assert road.attrib['id'] == '1' and float(road.attrib['length']) >= 2 * FEET_500_M
    assert len(road.findall('.//lane[@type="driving"]')) == 2
    assert len(road.findall('.//elevation')) >= 2
    validate_route(route())
    return {'arc_radius_m': 115.0, 'two_way_lanes': True,
            'crest_profile_authored': True, 'route_phase_count': 3,
            'physical_world_and_body_envelope_unverified': True}
