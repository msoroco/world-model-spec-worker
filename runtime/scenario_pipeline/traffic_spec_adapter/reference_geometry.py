"""Conservative component envelopes for declared source render-reference estimates.

Enclosure intersections remain unknown. Positive hits require separately
source-qualified opaque triangles and a robust crossing proof. Geometry and
configuration coverage must be source-qualified before either predicate is used.
"""
import math
import itertools
import numpy as np


def _vector(value):
    value = np.asarray(value, dtype=float)
    if value.shape != (3,) or not np.isfinite(value).all():
        raise ValueError('Invalid reference geometry vector')
    return value


def _box_candidates(a, b, low, high, margin):
    """A miss excludes every expanded box, including parallel/contact cases."""
    enter = np.zeros(len(low))
    leave = np.ones(len(low))
    alive = np.ones(len(low), dtype=bool)
    for axis in range(3):
        lo, hi = low[:, axis]-margin, high[:, axis]+margin
        delta = b[axis]-a[axis]
        if delta == 0:
            alive &= (a[axis] >= lo) & (a[axis] <= hi)
        else:
            first, last = (lo-a[axis])/delta, (hi-a[axis])/delta
            enter = np.maximum(enter, np.minimum(first, last))
            leave = np.minimum(leave, np.maximum(first, last))
            alive &= enter <= leave
    return np.flatnonzero(alive)


def _triangle_prism(triangle):
    """Enclosing halfspaces; ill-conditioned faces retain their outer box."""
    eps = np.finfo(float).eps
    scale = max(1., float(np.max(np.abs(triangle))))
    edges = [triangle[(i+1)%3]-triangle[i] for i in range(3)]
    lengths = [float(np.linalg.norm(edge)) for edge in edges]
    normal = np.cross(edges[0], triangle[2]-triangle[0])
    area = float(np.linalg.norm(normal))
    if min(lengths) <= 1024*eps*scale or area <= 1024*eps*max(lengths)**2:
        return None
    normal /= area
    normals = [normal, -normal]
    for i, edge in enumerate(edges):
        inward = np.cross(normal, edge)
        inward /= np.linalg.norm(inward)
        if np.dot(inward, triangle[(i+2)%3]-triangle[i]) <= 1024*eps*scale:
            return None
        normals.append(-inward)
    normals = np.asarray(normals)
    # Maxima over all vertices explicitly enclose the complete triangle even
    # when a calculated edge plane is perturbed by floating-point arithmetic.
    offsets = np.max(normals @ triangle.T, axis=1)
    return normals, offsets, scale


def _prism_possible(a, b, prism, margin):
    if prism is None:return True
    normals, offsets, scale = prism
    eps = np.finfo(float).eps
    scale = max(scale, float(np.max(np.abs(a))), float(np.max(np.abs(b))))
    offsets = offsets+margin*np.abs(normals).sum(axis=1)+1024*eps*scale
    low, high, delta = 0., 1., b-a
    guard = 2048*eps*scale
    for normal, offset in zip(normals, offsets):
        start = float(np.dot(normal, a)-offset)
        slope = float(np.dot(normal, delta))
        if abs(slope) <= guard:
            if min(start, start+slope) > guard:return False
            continue
        bound = (-start+guard)/slope
        widening = 2048*eps*max(1., abs(bound))
        if slope > 0:high = min(high, bound+widening)
        else:low = max(low, bound-widening)
        if low > high:return False
    return True


def _triangle_box_section(a, b, triangle, margin):
    """Enclose a robust opposite-side plane section in barycentric coordinates.

    An opposite-side plane section of the convex hull of two boxes is enclosed
    by their corner-pair intersections.
    Contact or poor conditioning stays unknown. The section is shared by the
    positive crossing and negative separating-edge proofs.
    """
    a, b = _vector(a), _vector(b)
    triangle = np.asarray(triangle, dtype=float)
    if (triangle.shape != (3, 3) or not np.isfinite(triangle).all()
            or type(margin) not in (int, float) or not math.isfinite(margin)
            or margin <= 0):
        raise ValueError('Invalid positive reference triangle inputs')
    edges = np.stack((triangle[1]-triangle[0], triangle[2]-triangle[0]), axis=1)
    singular = np.linalg.svd(edges, compute_uv=False)
    eps = np.finfo(float).eps
    if singular[0] == 0 or singular[1] <= 1024*eps*singular[0]:
        return None
    normal = np.cross(edges[:, 0], edges[:, 1])
    normal /= np.linalg.norm(normal)
    corners = np.asarray(list(itertools.product((-1., 1.), repeat=3)))*margin
    aa, bb = a+corners, b+corners
    scale = max(1., float(np.max(np.abs(np.concatenate((aa.ravel(), bb.ravel(), triangle.ravel()))))))
    guard = 65536*eps*scale
    sa, sb = (aa-triangle[0]) @ normal, (bb-triangle[0]) @ normal
    if not ((sa.min() > guard and sb.max() < -guard)
            or (sa.max() < -guard and sb.min() > guard)):
        return None
    fraction = sa[:, None]/(sa[:, None]-sb[None, :])
    points = (aa[:, None, :]+fraction[:, :, None]*(bb[None, :, :]-aa[:, None, :])).reshape(-1, 3)
    basis = np.linalg.pinv(edges)
    weights = (points-triangle[0]) @ basis.T
    weights = np.column_stack((1-weights.sum(axis=1), weights))
    guard *= max(1., float(np.linalg.norm(basis, ord=np.inf)))
    return (weights, guard) if np.isfinite(weights).all() else None


def segment_box_crosses_triangle(a, b, triangle, margin):
    """Every endpoint-box segment crosses the fixed triangle; opacity separate."""
    section = _triangle_box_section(a, b, triangle, margin)
    return section is not None and bool(section[0].min() > section[1])


def segment_box_misses_triangle(a, b, triangle, margin):
    """A complete plane section strictly outside one source edge proves a miss."""
    section = _triangle_box_section(a, b, triangle, margin)
    return section is not None and bool(np.any(section[0].max(axis=0) < -section[1]))


def segment_box_crosses_triangle_fan(a, b, triangles, margin):
    """Prove a hit across a continuous source triangle fan, including seams.

    Project a nonoverlapping disk of triangles onto a plane. All source heights
    lie in a slab; all endpoint-box ray sections must lie strictly in the
    projected boundary's kernel throughout that slab. The continuous surface
    then separates the two endpoint boxes. Opacity is a separate caller proof.
    Contact, missing faces, folds and uncertain topology remain unknown.
    """
    a, b = _vector(a), _vector(b)
    triangles = np.asarray(triangles, dtype=float)
    if (triangles.ndim != 3 or triangles.shape[1:] != (3, 3)
            or not np.isfinite(triangles).all()
            or type(margin) not in (int, float) or not math.isfinite(margin)
            or margin <= 0):
        raise ValueError('Invalid positive reference triangle fan inputs')
    if len(triangles) < 2:
        return False
    faces = [[tuple(p) for p in face] for face in triangles]
    if not set.intersection(*(set(face) for face in faces)):
        return False
    vertices = np.unique(triangles.reshape(-1, 3), axis=0)
    origin = vertices.mean(axis=0)
    _, singular, axes = np.linalg.svd(vertices-origin, full_matrices=False)
    if len(singular) < 2 or singular[1] <= 1024*np.finfo(float).eps*singular[0]:
        return False
    basis, normal = axes[:2], axes[2]
    if np.dot(np.cross(basis[0], basis[1]), normal) < 0:
        basis = basis.copy(); basis[1] *= -1
    scale = max(1., float(np.max(np.abs(np.concatenate((a, b, vertices.ravel()))))))
    guard = 65536*np.finfo(float).eps*scale
    projected = {tuple(p): (p-origin) @ basis.T for p in vertices}
    def cross(x, y):
        return float(x[0]*y[1]-x[1]*y[0])
    edges = {}
    for face in faces:
        x, y, z = [projected[p] for p in face]
        area = cross(y-x, z-x)
        if abs(area) <= guard*max(1., float(np.linalg.norm(y-x)), float(np.linalg.norm(z-x))):
            return False
        if area < 0:
            face = list(reversed(face))
        for x, y in zip(face, face[1:]+face[:1]):
            edges.setdefault(tuple(sorted((x, y))), []).append((x, y))
    if any(len(rows) > 2 or (len(rows) == 2 and rows[0] != rows[1][::-1])
           for rows in edges.values()):
        return False
    boundary = [rows[0] for rows in edges.values() if len(rows) == 1]
    outgoing = dict(boundary)
    if (not boundary or len(outgoing) != len(boundary)
            or len({y for _, y in boundary}) != len(boundary)):
        return False
    start = boundary[0][0]; visited = set(); current = start
    while current in outgoing and current not in visited:
        visited.add(current); current = outgoing[current]
    if current != start or len(visited) != len(boundary):
        return False
    # Disjoint projected edges and consistently oriented internal edges establish
    # a single-valued disk, rather than filling gaps with a convex hull.
    for (u, v), (w, z) in itertools.combinations(edges, 2):
        shared = {u, v} & {w, z}
        if shared:
            p = next(iter(shared)); x = projected[next(t for t in (u, v) if t != p)]-projected[p]
            y = projected[next(t for t in (w, z) if t != p)]-projected[p]
            if abs(cross(x, y)) <= guard*max(1., float(np.linalg.norm(x)), float(np.linalg.norm(y))) and np.dot(x, y) >= 0:
                return False
            continue
        x, y, p, q = [projected[t] for t in (u, v, w, z)]
        separated = np.any(np.maximum(x, y)+guard < np.minimum(p, q)) or np.any(np.maximum(p, q)+guard < np.minimum(x, y))
        for s, t, c, d in [(x, y, p, q), (p, q, x, y)]:
            h = guard*max(1., float(np.linalg.norm(t-s)))
            lo, hi = sorted((cross(t-s, c-s), cross(t-s, d-s)))
            separated = separated or lo > h or hi < -h
        if not separated:
            return False
    corners = np.asarray(list(itertools.product((-1., 1.), repeat=3)))*margin
    aa, bb = a+corners, b+corners
    sa, sb = (aa-origin) @ normal, (bb-origin) @ normal
    low, high = ((vertices-origin) @ normal).min()-guard, ((vertices-origin) @ normal).max()+guard
    if not ((sa.max() < low and sb.min() > high) or (sb.max() < low and sa.min() > high)):
        return False
    cuts = []
    for height in (low, high):
        fraction = (height-sa[:, None])/(sb[None, :]-sa[:, None])
        cuts.append((aa[:, None, :]+fraction[:, :, None]*(bb[None, :, :]-aa[:, None, :])).reshape(-1, 3))
    points = (np.concatenate(cuts)-origin) @ basis.T
    for u, v in boundary:
        x, y = projected[u], projected[v]; edge = y-x
        distances = edge[0]*(points[:, 1]-x[1])-edge[1]*(points[:, 0]-x[0])
        if not np.isfinite(distances).all() or distances.min() <= guard*max(1., float(np.linalg.norm(edge))):
            return False
    return True


def segment_box_mask_is_opaque(a, b, triangle, margin, uv, alpha, cutoff):
    """Require every bilinear contributor over the full ray section opaque.

    UVs use the source-qualified unflipped base-mip image-row convention.
    Sampling outside the retained image remains unknown; no wrap is guessed.
    """
    if not segment_box_crosses_triangle(a, b, triangle, margin):
        return False
    a, b, triangle = _vector(a), _vector(b), np.asarray(triangle, dtype=float)
    edges = np.stack((triangle[1]-triangle[0], triangle[2]-triangle[0]), axis=1)
    normal = np.cross(edges[:, 0], edges[:, 1]); normal /= np.linalg.norm(normal)
    corners = np.asarray(list(itertools.product((-1., 1.), repeat=3)))*margin
    aa, bb = a+corners, b+corners
    sa, sb = (aa-triangle[0]) @ normal, (bb-triangle[0]) @ normal
    fraction = sa[:, None]/(sa[:, None]-sb[None, :])
    points = (aa[:, None, :]+fraction[:, :, None]*(bb[None, :, :]-aa[:, None, :])).reshape(-1, 3)
    basis = np.linalg.pinv(edges)
    weights = (points-triangle[0]) @ basis.T
    weights = np.column_stack((1-weights.sum(axis=1), weights))
    coords = weights @ uv
    scale = max(1., float(np.max(np.abs(np.concatenate((aa.ravel(), bb.ravel(), triangle.ravel()))))))
    slack = 65536*np.finfo(float).eps*scale*max(1., float(np.linalg.norm(basis, ord=np.inf)))*max(1., 3*float(np.abs(uv).max()))
    low, high = coords.min(axis=0)-slack, coords.max(axis=0)+slack
    height, width = alpha.shape
    x0, y0 = np.floor(low*np.array([width, height])).astype(np.int64)-1
    x1, y1 = np.ceil(high*np.array([width, height])).astype(np.int64)+1
    if x0 < 0 or y0 < 0 or x1 >= width or y1 >= height:
        return False
    return bool(alpha[y0:y1+1, x0:x1+1].min() >= math.ceil(cutoff*255)+2)


class ReferenceComponentGeometry:
    """Actor-local metres: triangle boxes, swept doors, all-rotation wheels."""
    def __init__(self, triangles, door_low, door_high, wheel_centers,
                 wheel_radii, wheel_travel_m):
        triangles = np.asarray(triangles, dtype=float)
        door_low, door_high = [np.asarray(x, dtype=float) for x in (door_low, door_high)]
        centers, radii = np.asarray(wheel_centers, dtype=float), np.asarray(wheel_radii, dtype=float)
        if (triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not len(triangles)
                or door_low.ndim != 2 or door_low.shape[1:] != (3,) or door_high.shape != door_low.shape
                or centers.ndim != 2 or centers.shape[1:] != (3,) or radii.shape != (len(centers),)
                or any(not np.isfinite(x).all() for x in (triangles, door_low, door_high, centers, radii))
                or np.any(door_low > door_high) or np.any(radii <= 0)
                or type(wheel_travel_m) not in (float, int) or not math.isfinite(wheel_travel_m)
                or wheel_travel_m < 0):
            raise ValueError('Invalid complete reference component geometry')
        self.prisms = [_triangle_prism(triangle) for triangle in triangles]
        self.triangles = triangles
        self.triangles.flags.writeable = False
        self.opaque_indices = np.empty(0, dtype=np.int64)
        self.opaque_indices.flags.writeable = False
        self.mask_faces = {}
        self.single_sided_indices = frozenset()
        self.fresnel_faces = {}
        self.triangle_count, self.door_count = len(triangles), len(door_low)
        self.low = np.concatenate((triangles.min(axis=1), door_low))
        self.high = np.concatenate((triangles.max(axis=1), door_high))
        self.centers, self.radii = centers.copy(), radii.copy()+wheel_travel_m
        all_low = np.concatenate((self.low, centers-self.radii[:, None]))
        all_high = np.concatenate((self.high, centers+self.radii[:, None]))
        self.aggregate_low, self.aggregate_high = all_low.min(axis=0)[None, :], all_high.max(axis=0)[None, :]
        for array in (self.low, self.high, self.centers, self.radii,
                      self.aggregate_low, self.aggregate_high):
            array.flags.writeable = False

    @classmethod
    def load(cls, path, wheel_travel_m):
        with np.load(path, allow_pickle=False) as data:
            names = ('rigid_triangles', 'door_low', 'door_high', 'wheel_centers', 'wheel_radii')
            if set(data.files) != set(names):
                raise ValueError('Unexpected reference component buffers')
            return cls(*(data[name] for name in names), wheel_travel_m)

    def qualify_opaque_masks(self, indices, uv, alpha, cutoff):
        indices, uv, alpha = np.asarray(indices), np.asarray(uv), np.asarray(alpha)
        if (indices.ndim != 1 or indices.dtype.kind not in 'iu' or not len(indices)
                or np.any(indices < 0) or np.any(indices >= self.triangle_count)
                or np.any(indices[1:] <= indices[:-1])
                or uv.shape != (len(indices), 3, 2) or uv.dtype.kind not in 'fiu'
                or not np.isfinite(uv).all()
                or alpha.ndim != 2 or not alpha.size or alpha.dtype != np.uint8
                or type(cutoff) not in (int, float) or not math.isfinite(cutoff)
                or not 0 <= cutoff < 1
                or any(int(index) in self.fresnel_faces for index in indices)):
            raise ValueError('Invalid source-qualified ray mask inputs')
        alpha = alpha.copy(); alpha.flags.writeable = False
        for index, coords in zip(indices, uv):
            coords = coords.astype(float, copy=True); coords.flags.writeable = False
            self.mask_faces[int(index)] = (coords, alpha, cutoff)

    def qualify_opaque_triangles(self, indices):
        """Attach a separately source-qualified subset, not an opacity guess."""
        values = np.asarray(indices)
        if (values.ndim != 1 or values.dtype.kind not in 'iu' or not len(values)
                or np.any(values >= self.triangle_count) or np.any(values < 0)
                or np.any(values[1:] <= values[:-1])
                or any(int(value) in self.fresnel_faces for value in values)):
            raise ValueError('Invalid source-qualified opaque triangle subset')
        self.opaque_indices = values.astype(np.int64, copy=True)
        self.opaque_indices.flags.writeable = False

    def qualify_single_sided_triangles(self, indices):
        """Bind source-qualified original UE winding, under default view flags."""
        values = np.asarray(indices)
        if (values.ndim != 1 or values.dtype.kind not in 'iu'
                or np.any(values < 0) or np.any(values >= self.triangle_count)
                or np.any(values[1:] <= values[:-1])):
            raise ValueError('Invalid source-qualified single-sided triangle subset')
        self.single_sided_indices = frozenset(map(int, values))

    def face_side(self, index, observer, margin):
        """Positive means culled; negative means retained; contact is unknown."""
        triangle = self.triangles[index]
        normal = np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])
        length = float(np.linalg.norm(normal))
        edge_scale = max(float(np.linalg.norm(triangle[1]-triangle[0])),
                         float(np.linalg.norm(triangle[2]-triangle[0])))
        if length <= 1024*np.finfo(float).eps*edge_scale**2:
            return 0
        normal /= length
        scale = max(1., float(np.max(np.abs(triangle))), float(np.max(np.abs(observer))))
        guard = margin*float(np.abs(normal).sum())+65536*np.finfo(float).eps*scale
        distance = float(np.dot(normal, observer-triangle[0]))
        return 1 if distance > guard else -1 if distance < -guard else 0

    def qualify_fresnel_transmission(self, indices, normals, intensity, exponent):
        """Source-bound glass normals and alpha=I+(1-I)*F**exponent."""
        indices, normals = np.asarray(indices), np.asarray(normals, dtype=float)
        if (indices.ndim != 1 or indices.dtype.kind not in 'iu' or not len(indices)
                or np.any(indices < 0) or np.any(indices >= self.triangle_count)
                or np.any(indices[1:] <= indices[:-1])
                or normals.shape != (len(indices), 3, 3) or not np.isfinite(normals).all()
                or np.any(np.linalg.norm(normals, axis=2) == 0)
                or type(intensity) not in (float, int) or not math.isfinite(intensity)
                or not 0 <= intensity < 1
                or type(exponent) not in (float, int) or not math.isfinite(exponent)
                or exponent <= 0 or np.intersect1d(indices, self.opaque_indices).size
                or any(int(index) in self.mask_faces for index in indices)):
            raise ValueError('Invalid source-qualified glass transmission')
        normals = normals.copy(); normals.flags.writeable = False
        self.fresnel_faces = {int(index): normal for index, normal in zip(indices, normals)}
        self.fresnel_intensity, self.fresnel_exponent = intensity, exponent

    def proves_transmission(self, index, observer, target, margin):
        """Bound every interpolated source normal and endpoint-box direction.

        Numerical guards enclose the reference calculation; they are not a
        calibrated measurement error or an invented optical threshold.
        """
        normals = self.fresnel_faces.get(index)
        if normals is None:
            return False
        direction = observer-target
        normal_margin = 64*2**-23*max(1., float(np.max(np.abs(normals))))
        error = (2*margin*np.abs(normals).sum(axis=1)
                 +normal_margin*(float(np.abs(direction).sum())+6*margin))
        lower = float(np.min(normals @ direction-error))
        denominator = ((float(np.linalg.norm(normals, axis=1).max())+math.sqrt(3)*normal_margin)
                       *(float(np.linalg.norm(direction))+2*math.sqrt(3)*margin))
        if lower > 0 and denominator > 0:
            fresnel = max(1-lower/denominator, .0001)
            alpha = (self.fresnel_intensity+(1-self.fresnel_intensity)
                     *fresnel**self.fresnel_exponent+1024*2**-23)
            if alpha < 1:
                return True
        # The complete plane section bounds the actual interpolation region.
        # A remote vertex normal need not describe any possible ray crossing.
        if margin <= 0:
            return False
        section = _triangle_box_section(observer, target, self.triangles[index], margin)
        if section is None:
            return False
        weights, weight_guard = section
        local_normals = weights @ normals
        weight_size = max(1., float(np.abs(weights).sum(axis=1).max())+3*weight_guard)
        normal_error = (normal_margin*weight_size
                        +weight_guard*np.abs(normals).sum(axis=0))
        error = (2*margin*np.abs(local_normals).sum(axis=1)
                 +(normal_error*(np.abs(direction)+2*margin)).sum())
        lower = float(np.min(local_normals @ direction-error))
        denominator = ((float(np.linalg.norm(local_normals, axis=1).max())
                        +float(np.linalg.norm(normal_error)))
                       *(float(np.linalg.norm(direction))+2*math.sqrt(3)*margin))
        if lower <= 0 or denominator <= 0:
            return False
        fresnel = max(1-lower/denominator, .0001)
        alpha = (self.fresnel_intensity+(1-self.fresnel_intensity)
                 *fresnel**self.fresnel_exponent+1024*2**-23)
        return bool(alpha < 1)


class ReferenceActorGeometry:
    def __init__(self, components, origin, axes, source_margin_m):
        self.components, self.origin = components, _vector(origin)
        self.axes = np.asarray(axes, dtype=float)
        if (self.axes.shape != (3, 3) or not np.isfinite(self.axes).all()
                or np.max(np.abs(self.axes @ self.axes.T-np.eye(3))) > 1e-12
                or type(source_margin_m) not in (float, int)
                or not math.isfinite(source_margin_m) or source_margin_m <= 0):
            raise ValueError('Invalid original-root reference transform or source margin')
        self.source_margin_m = source_margin_m

    def proves_opaque_hit(self, observer, target, source_margin_m):
        """Positive proof under the qualified source model and query margin."""
        observer, target = _vector(observer), _vector(target)
        if (type(source_margin_m) not in (float, int)
                or not math.isfinite(source_margin_m) or source_margin_m <= 0):
            raise ValueError('Invalid positive source query margin')
        model = self.components
        if not len(model.opaque_indices) and not model.mask_faces:
            return False
        a, b = self.axes @ (observer-self.origin), self.axes @ (target-self.origin)
        margin = source_margin_m+64*2**-52*max(
            1., float(np.max(np.abs(np.concatenate((observer, target, self.origin, a, b))))))
        indices = model.opaque_indices
        candidates = _box_candidates(a, b, model.low[indices], model.high[indices], margin)
        eligible = [int(indices[i]) for i in candidates
                    if int(indices[i]) not in model.single_sided_indices
                    or model.face_side(int(indices[i]), a, margin) == -1]
        if any(segment_box_crosses_triangle(a, b, model.triangles[i], margin) for i in eligible):
            return True
        possible = [i for i in eligible if _prism_possible(a, b, model.prisms[i], margin)]
        if segment_box_crosses_triangle_fan(a, b, model.triangles[possible], margin):
            return True
        mask_indices = np.asarray(list(model.mask_faces), dtype=np.int64)
        for i in _box_candidates(a, b, model.low[mask_indices], model.high[mask_indices], margin):
            index = int(mask_indices[i])
            if index in model.single_sided_indices and model.face_side(index, a, margin) != -1:
                continue
            uv, alpha, cutoff = model.mask_faces[index]
            if segment_box_mask_is_opaque(a, b, model.triangles[index], margin, uv, alpha, cutoff):
                return True
        return False

    def intersects(self, observer, target):
        observer, target = _vector(observer), _vector(target)
        a, b = self.axes @ (observer-self.origin), self.axes @ (target-self.origin)
        scale = max(1., float(np.max(np.abs(np.concatenate((observer, target, self.origin, a, b))))))
        # The body encoding budget is shared. Observer/local-coordinate encoding
        # depends on this query, not a different distant probe in the frame.
        margin = max(self.source_margin_m, 64*2**-23*scale)+64*2**-52*scale
        model = self.components
        # Broad phase belongs to this complete model, not the original API body
        # box: doors and suspension may extend beyond that earlier estimate.
        if not len(_box_candidates(a, b, model.aggregate_low, model.aggregate_high, margin)):
            return False
        for index in _box_candidates(a, b, model.low, model.high, margin):
            if (index in model.single_sided_indices
                    and model.face_side(index, a, margin) == 1):
                continue
            if index < model.triangle_count and model.proves_transmission(index, a, b, margin):
                continue
            if index >= model.triangle_count or (
                    _prism_possible(a, b, model.prisms[index], margin)
                    and not segment_box_misses_triangle(a, b, model.triangles[index], margin)):
                return True
        delta = b-a
        length_squared = float(np.dot(delta, delta))
        for center, radius in zip(model.centers, model.radii):
            t = 0. if length_squared == 0 else min(1., max(0., float(np.dot(center-a, delta))/length_squared))
            if float(np.linalg.norm(a+t*delta-center)) <= radius+margin:
                return True
        return False
