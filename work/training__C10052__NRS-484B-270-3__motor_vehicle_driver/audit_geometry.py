"""Independent polygon/rectangle intersection for C10052 receipt audits."""


def clipped_area(vertices, bounds):
    polygon = [tuple(point) for point in vertices]
    for axis, boundary, greater in ((0, bounds[0], True), (0, bounds[2], False),
                                    (1, bounds[1], True), (1, bounds[3], False)):
        output = []
        previous = polygon[-1] if polygon else None
        for point in polygon:
            in_point = point[axis] >= boundary if greater else point[axis] <= boundary
            in_previous = previous[axis] >= boundary if greater else previous[axis] <= boundary
            if in_point != in_previous:
                fraction = (boundary - previous[axis]) / (point[axis] - previous[axis])
                output.append(tuple(previous[k] + fraction * (point[k] - previous[k])
                                    for k in (0, 1)))
            if in_point:
                output.append(point)
            previous = point
        polygon = output
    return abs(sum(p[0]*q[1]-q[0]*p[1]
                   for p, q in zip(polygon, polygon[1:]+polygon[:1])))/2 if polygon else 0.0


def footprint_gap(vertices, bounds):
    from math import hypot
    x_min=min(point[0] for point in vertices)
    x_max=max(point[0] for point in vertices)
    y_min=min(point[1] for point in vertices)
    y_max=max(point[1] for point in vertices)
    return hypot(max(bounds[0]-x_max,x_min-bounds[2],0),
                 max(bounds[1]-y_max,y_min-bounds[3],0))
