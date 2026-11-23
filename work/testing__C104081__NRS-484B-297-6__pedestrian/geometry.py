"""Authored cross section and route for NRS 484B.297(6) CPU preparation.

Coordinates are local engineering metres, not a surveyed CARLA map or a legal
finding. The operator must bind these shapes to a verified sidewalk/highway.
"""

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Rectangle:
    name: str
    x0: float
    x1: float
    y0: float
    y1: float

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass(frozen=True)
class Scene:
    case_id: str
    direction: int
    sidewalk_end: float
    area_blocked: bool
    obstruction_kind: str
    sidewalk: Rectangle
    intervening_area: Rectangle
    designated_lane: Rectangle
    highway: Rectangle
    obstacles: tuple[Rectangle, ...]
    missing_sections: tuple[Rectangle, ...]
    route: tuple[tuple[float, float], ...]


def construct(case_id: str, *, direction: int = 1, area_blocked: bool = False,
              sidewalk_end: float = 34.0, obstruction_kind: str = "impassable_section") -> Scene:
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    if sidewalk_end not in (34.0, 40.0):
        raise ValueError("unsupported authored sidewalk end")
    if obstruction_kind not in ("impassable_section", "missing_section"):
        raise ValueError("unsupported obstruction kind")
    sidewalk = Rectangle("sidewalk", 0, 60, 4, 6)
    area = Rectangle("intervening_area", 0, 60, 2, 4)
    lane = Rectangle("designated_bicycle_lane", 0, 60, 0, 2)
    highway = Rectangle("immediately_adjacent_highway", 0, 60, -3, 4)
    obstacles = []
    missing_sections = []
    if obstruction_kind == "missing_section":
        missing_sections.append(Rectangle("missing_sidewalk_surface", 20, sidewalk_end, 4, 6))
    else:
        obstacles.append(Rectangle("impassable_sidewalk_section", 20, sidewalk_end, 4, 6))
    if area_blocked:
        obstacles.append(Rectangle("intervening_barrier", 20, sidewalk_end, 2, 4))
    bypass_y = 1.0 if area_blocked else 3.0
    if direction == 1:
        route = ((10, 5), (17, 5), (18, bypass_y),
                 (sidewalk_end + 2, bypass_y), (sidewalk_end + 3, 5), (50, 5))
    else:
        route = ((50, 5), (sidewalk_end + 3, 5),
                 (sidewalk_end + 2, bypass_y), (18, bypass_y), (17, 5), (10, 5))
    return Scene(case_id, direction, sidewalk_end, area_blocked, obstruction_kind,
                 sidewalk, area, lane, highway, tuple(obstacles), tuple(missing_sections), route)


def sample_route(route: tuple[tuple[float, float], ...], step: float = 0.05):
    """Yield dense engineering samples, including endpoints, for obstruction checks."""
    for (ax, ay), (bx, by) in zip(route, route[1:]):
        n = max(1, int(hypot(bx - ax, by - ay) / step) + 1)
        for i in range(n + 1):
            t = i / n
            yield ax + t * (bx - ax), ay + t * (by - ay)


def audit_design(scene: Scene) -> dict:
    """Check authored shapes; never infer statutory due care or impassability."""
    if scene.intervening_area.y1 != scene.sidewalk.y0:
        raise ValueError("intervening area does not border sidewalk")
    if scene.designated_lane.y1 != scene.intervening_area.y0:
        raise ValueError("designated lane does not border intervening area")
    if scene.highway.y1 != scene.sidewalk.y0:
        raise ValueError("highway is not adjacent to sidewalk")
    sidewalk_blocks = scene.obstacles if scene.obstruction_kind == "impassable_section" else scene.missing_sections
    if not any(o.x0 == 20 and o.x1 == scene.sidewalk_end and
               o.y0 == scene.sidewalk.y0 and o.y1 == scene.sidewalk.y1 for o in sidewalk_blocks):
        raise ValueError("sidewalk obstruction is not constructed")
    if scene.area_blocked != any(o.name == "intervening_barrier" for o in scene.obstacles):
        raise ValueError("intervening barrier does not match case")
    if scene.direction * (scene.route[-1][0] - scene.route[0][0]) <= 0:
        raise ValueError("route travels against authored direction")
    samples = tuple(sample_route(scene.route))
    if any(o.contains(x, y) for x, y in samples for o in (*scene.obstacles, *scene.missing_sections)):
        raise ValueError("pedestrian route intersects constructed obstruction")
    in_lane = any(scene.designated_lane.y0 < y < scene.designated_lane.y1
                  for _, y in samples)
    if in_lane != scene.area_blocked:
        raise ValueError("designated-lane use is not isolated to blocked-area case")
    if not any(20 <= x <= scene.sidewalk_end for x, _ in samples):
        raise ValueError("route misses obstruction interval")
    if not scene.sidewalk.contains(*scene.route[0]) or not scene.sidewalk.contains(*scene.route[-1]):
        raise ValueError("route does not start and return on sidewalk")
    return {"case_id": scene.case_id, "sample_count": len(samples),
            "designated_lane_used": in_lane, "obstacle_count": len(scene.obstacles),
            "missing_surface_count": len(scene.missing_sections),
            "obstruction_kind": scene.obstruction_kind,
            "engineering_route_clear": True, "legal_judgment": "unresolved"}
