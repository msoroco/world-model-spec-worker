"""Prospective capture contract; no change to existing frozen recordings."""
PROFILE = {'version': 'overview1080-capability-v1', 'status': 'capability_only',
           'fps': 20, 'overview': [1920, 1080],
           'detail_views': [[1280, 720], [1280, 720], [1280, 720]],
           'encoding': 'retain_existing_lossless',
           'required_checks': ['all required participant body histories visible',
                               'physical signs and governed approaches legible',
                               'stop lines/crosswalks/boundaries visible',
                               'startup through clearance and final observation retained']}


def layout(overview, details, header=0):
    if len(details) != 3 or any(w <= 0 or h <= 0 for w, h in [overview, *details]) or header < 0:
        raise ValueError('Expected positive overview and three detail dimensions')
    width = max(overview[0], sum(d[0] for d in details))
    rects = {'overview': [(width - overview[0]) // 2, header, *overview]}
    x = 0
    for key, (w, h) in zip(('approach', 'reference_corner', 'driver_reference'), details):
        rects[key] = [x, header + overview[1], w, h]
        x += w
    return {'width': width, 'height': header + overview[1] + max(d[1] for d in details),
            'views': rects, 'unscaled': True}
