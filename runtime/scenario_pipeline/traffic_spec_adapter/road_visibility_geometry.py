"""Source-derived clearance inside a finite flat driving-road interior."""
import hashlib
import math

# These are the same official generation sources used by the shared reader.
SOURCES = {
    'Map.cpp': 'c123ab21ad8770d42824660ab8f50bc2045a95b16277a026aeaef3ad0667f209',
    'MeshFactory.cpp': '24984f06eccd8d11ed91d89f939a7a544e6866fbfa5883e7901b48904243ae14',
    'Lane.cpp': '53adedca967bf6e617bc47b861307a37e831baa604f0fae165577deec1704289',
    'OpenDriveGenerator.cpp': 'aa55d2967c7c01796bd277e8fb64bd7b4a85a67e5104bdec9ba4790456deb2ff',
}


class FlatRoadInterior:
    """Convex interior excludes source-generated outer walls, not other actors."""
    def __init__(self, x, y, heading, length, left, right, ceiling):
        self.x, self.y, self.heading = x, y, heading
        self.length, self.left, self.right, self.ceiling = length, left, right, ceiling

    def provenance(self):
        return {'method':'source_bound_finite_flat_road_interior_v1',
                'source_origin_opendrive_m':[self.x,self.y],
                'source_heading_rad':self.heading,'source_length_m':self.length,
                'source_driving_widths_left_right_m':[self.left,self.right],
                'global_geometry_ceiling_m':self.ceiling,'source_floor_z_m':0.,
                'domain':'strict finite convex driving-road strip; XY source-construction guard',
                'outside_domain':'retain global geometry ceiling',
                'other_scene_objects':'all existing qualified actor/object checks retained'}

    def clearance(self, observer, target):
        fallback = min(observer[2], target[2]) - self.ceiling
        c, s = math.cos(self.heading), math.sin(self.heading)
        scale = max(1., self.length, abs(self.x), abs(self.y), self.left, self.right,
                    *(abs(v) for p in (observer, target) for v in p))
        # Cover source world vertices, lane arithmetic, and query Float32 joins.
        margin = 128 * 2**-23 * scale * (1 + abs(c) + abs(s))
        for p in (observer, target):
            dx, dy = p[0] - self.x, p[1] + self.y
            station, lateral = c * dx - s * dy, -s * dx - c * dy
            if not (margin < station < self.length - margin
                    and -self.right + margin < lateral < self.left - margin):
                return fallback
        # Every convex combination stays inside the verified finite road strip.
        # Its source surface is z=0; walls are on outer lane edges outside it.
        # All source Z coefficients and bank/offset heights are exactly zero.
        # XY construction error does not become invented vertical terrain error.
        height_guard = 64 * 2**-52 * max(1., abs(observer[2]), abs(target[2]))
        return max(fallback, min(observer[2], target[2]) - height_guard)


def flat_road_interior(xml, ceiling):
    """Return None outside the demonstrated single, flat, straight source family."""
    roads = xml.findall('road')
    if len(roads) != 1 or xml.findall('junction'):
        return None
    road = roads[0]
    if road.get('junction') != '-1' or any(road.findall(p) for p in
            ('./link/*', './objects/*', './signals/*', './surface/*', './lateralProfile/shape')):
        return None
    plans, sections = road.findall('./planView/geometry'), road.findall('./lanes/laneSection')
    if len(plans) != 1 or len(sections) != 1:
        return None
    g, section = plans[0], sections[0]
    def number(node, key, default=None):
        v = float(node.get(key, default))
        if not math.isfinite(v):
            raise ValueError('Nonfinite road interior geometry')
        return v
    length = number(road, 'length')
    if (length <= 0 or g.find('line') is None or len(list(g)) != 1
            or number(g, 's') != 0 or number(g, 'length') != length
            or number(section, 's') != 0):
        return None
    for tag in ('elevation', 'superelevation', 'crossfall', 'laneOffset'):
        if any(number(n, k, '0') != 0 for n in road.iter(tag) for k in 'abcd'):
            return None
    widths = []
    for side in ('left', 'right'):
        lanes = sorted(section.findall(side + '/lane'), key=lambda n: abs(int(n.get('id'))))
        if [abs(int(n.get('id'))) for n in lanes] != list(range(1, len(lanes) + 1)):
            return None
        width, shoulder = 0., False
        for lane in lanes:
            records = lane.findall('width')
            if (lane.get('type') not in ('driving', 'shoulder') or lane.findall('height')
                    or lane.findall('border') or len(records) != 1):
                return None
            w = records[0]
            if number(w, 'sOffset') != 0 or any(number(w, k) != 0 for k in 'bcd'):
                return None
            a = number(w, 'a')
            if a <= 0 or lane.get('type') == 'driving' and shoulder:
                return None
            if lane.get('type') == 'driving':width += a
            else:shoulder = True
        widths.append(width)
    if not any(widths):return None
    return FlatRoadInterior(number(g, 'x'), number(g, 'y'), number(g, 'hdg'),
                            length, widths[0], widths[1], ceiling)


def source_road_interior(xml, sources, ceiling, parameters):
    width=parameters.get('additional_width')
    if type(width)not in(int,float)or not math.isfinite(width)or width<0:return None
    if any(name not in sources or hashlib.sha256(sources[name].read_bytes()).hexdigest() != expected
           for name, expected in SOURCES.items()):
        return None
    return flat_road_interior(xml, ceiling)
