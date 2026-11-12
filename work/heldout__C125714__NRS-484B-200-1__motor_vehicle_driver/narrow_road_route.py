"""Select an engineered narrow median-opening route without legal classification."""

from directed_geometry import directed_road_section
from median_opening_route import select_median_opening_route


def select_narrow_median_route(world_map, reference, *, direction='east',
                               max_total_width_m=4.5):
    if max_total_width_m <= 0:
        raise ValueError('Engineering width bound must be positive')
    route, opening_samples = select_median_opening_route(
        world_map, reference, direction=direction)
    widths = []
    for waypoint in route:
        section = directed_road_section(waypoint, waypoint.get_left_lane())
        widths.append(section['subject_lane_width_m']+
                      section['opposite_lane_width_m'])
    if any(width > max_total_width_m for width in widths):
        raise ValueError('Sourced median-opening route is wider than engineered target')
    return route, opening_samples, widths
