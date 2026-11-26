"""Source-gated physical sampling plans for the two unresolved law phrases.

Setpoints are engineering coverage requests. No result here classifies legality.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from source_packet import validate_packet


@dataclass(frozen=True)
class SweepPoint:
    sweep: str
    rank: int
    requested_offset_m: float | None = None
    requested_gap_m: float | None = None


# Relative physical setpoints avoid inventing a City boundary or legal cutoff.
DESIGNATION_POINTS = (
    SweepPoint('designation_posting_source_review', 0, requested_offset_m=-2.0),
    SweepPoint('designation_posting_source_review', 1, requested_offset_m=0.0),
    SweepPoint('designation_posting_source_review', 2, requested_offset_m=2.0),
)
CONFLICT_POINTS = (
    SweepPoint('conflict_necessity_source_review', 0, requested_gap_m=4.0),
    SweepPoint('conflict_necessity_source_review', 1, requested_gap_m=8.0),
    SweepPoint('conflict_necessity_source_review', 2, requested_gap_m=12.0),
)


def _finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(name + ' must be finite')
    return float(value)


def preflight(packet_path: Path, case_id: str, point: SweepPoint,
              body_length_m: float) -> dict:
    """Resolve physical requests only after reviewed original sources validate."""
    site = validate_packet(packet_path, case_id)
    length = _finite(body_length_m, 'body length')
    if length <= 0:
        raise ValueError('body length must be positive')
    lo, hi = site['posted_interval_m']
    route = site['approach_waypoints']
    if point.sweep == 'designation_posting_source_review':
        if point not in DESIGNATION_POINTS:
            raise ValueError('unfrozen designation point')
        centre = hi + point.requested_offset_m
        if centre - length / 2 < route[0][0] or centre + length / 2 > route[-1][0]:
            raise ValueError('posted-boundary sweep point exceeds reviewed route')
        return {'sweep': point.sweep, 'rank': point.rank,
                'requested_body_interval_m': [centre - length / 2, centre + length / 2],
                'reviewed_posted_interval_m': [lo, hi], 'legal_judgment': None}
    if point.sweep == 'conflict_necessity_source_review':
        if point not in CONFLICT_POINTS:
            raise ValueError('unfrozen conflict point')
        if not site.get('traffic_conflict_source_sha256'):
            raise ValueError('reviewed lawful traffic-conflict source required')
        gap = _finite(point.requested_gap_m, 'requested gap')
        actor_route = site.get('conflict_actor_waypoints')
        if (gap <= 0 or not isinstance(actor_route, list) or len(actor_route) < 2 or
                any(not isinstance(p, list) or len(p) != 2 or
                    any(type(v) not in (int, float) or not isfinite(v) for v in p)
                    for p in actor_route)):
            raise ValueError('reviewed conflict actor route required')
        if actor_route[-1][0] - actor_route[0][0] < gap + length:
            raise ValueError('requested conflict gap exceeds reviewed actor route')
        return {'sweep': point.sweep, 'rank': point.rank,
                'requested_actor_gap_m': gap, 'legal_judgment': None}
    raise ValueError('unknown judgment sweep')


def measure_original(rows: list[dict], point: SweepPoint) -> dict:
    """Record original geometry and source identity without a judgment value."""
    if len(rows) < 3 or any(row.get('original_frame') != rows[0].get('original_frame') + i
                            for i, row in enumerate(rows)):
        raise ValueError('contiguous original sweep frames required')
    if point.sweep == 'designation_posting_source_review':
        measured = []
        for row in rows:
            west = _finite(row.get('body_west_x_m'), 'body west')
            east = _finite(row.get('body_east_x_m'), 'body east')
            boundary = _finite(row.get('reviewed_posted_end_x_m'), 'reviewed posted end')
            if east <= west or not row.get('posted_extent_sha256'):
                raise ValueError('original body or posted source missing')
            measured.append((west + east) / 2 - boundary)
        return {'sweep': point.sweep, 'rank': point.rank,
                'measured_offset_m': measured, 'legal_judgment': None}
    if point.sweep == 'conflict_necessity_source_review':
        measured = []
        actor_id = rows[0].get('conflict_actor_id')
        if not actor_id:
            raise ValueError('original conflict actor identity missing')
        for row in rows:
            gap = _finite(row.get('actual_actor_body_gap_m'), 'actual actor gap')
            if (gap < 0 or not row.get('traffic_conflict_source_sha256') or
                    row.get('conflict_actor_id') != actor_id):
                raise ValueError('original conflict source missing')
            measured.append(gap)
        return {'sweep': point.sweep, 'rank': point.rank,
                'measured_gap_m': measured, 'legal_judgment': None}
    raise ValueError('unknown judgment sweep')
