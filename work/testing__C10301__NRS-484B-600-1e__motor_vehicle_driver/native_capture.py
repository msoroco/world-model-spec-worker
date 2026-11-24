"""Exact-case Native acquisition, preserving original site, speed and media."""
from __future__ import annotations

from pathlib import Path
import json
import hashlib

from capture_finalizer import finalize_capture
from native_media import NativeMedia
from native_motion import capture_speed
from native_motion import CASE_PREFIX, TARGETS
from native_site import construct


def capture(world, packet_path: Path, attempt: Path, case_id: str,
            native_run_id: str, uncertainty_mps: float, transform_factory,
            control_factory, *, diagnostic_fixture=False,
            media_factory=NativeMedia):
    """Acquire one 900-tick run; clean up actors and writers on every exit.

    The caller owns world synchronous settings, traffic control and the reviewed
    route packet. This function never treats a diagnostic map as a real site.
    """
    packet = json.loads(Path(packet_path).read_text(encoding='utf-8'))
    if packet.get('diagnostic_fixture') is not diagnostic_fixture:
        raise ValueError('Native site and capture provenance differ')
    suffix = case_id.removeprefix(CASE_PREFIX)
    if case_id != CASE_PREFIX + suffix or suffix not in TARGETS:
        raise ValueError('unknown exact speed case')
    site = construct(world, packet_path, case_id, transform_factory)
    media = None
    try:
        attempt = Path(attempt)
        attempt.mkdir(parents=True, exist_ok=True)
        site_source = attempt / 'native-site-source.json'
        source_bytes = Path(packet_path).read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != site.packet_sha256:
            raise ValueError('Native site packet changed after construction')
        with site_source.open('xb') as stream:
            stream.write(source_bytes)
        setup = {'case_id': case_id, 'law_id': 'NRS-484B-600-1e',
                 'cell_id': packet['cell_id'], 'actor': packet['actor'],
                 'layout': packet['layout'], 'control': packet['control'],
                 'maneuver': packet['maneuver'],
                 'requested_speed_mph': TARGETS[suffix],
                 'native_site_sha256': site.packet_sha256}
        with (attempt / 'authored-setup.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(setup, indent=2, sort_keys=True) + '\n')
        media = media_factory(site.cameras, attempt,
                              diagnostic_fixture=diagnostic_fixture)
        motion = capture_speed(world, site.actor, control_factory, attempt,
                               case_id, native_run_id, uncertainty_mps,
                               diagnostic_fixture=diagnostic_fixture,
                               camera_frame_reader=media.read,
                               route_reader=site.observe_route)
        frames, paths = media.finish()
        index = finalize_capture(attempt, case_id, frames, paths,
                                 site_source=site_source)
        return {'motion': motion, 'capture_index': index,
                'site_packet_sha256': site.packet_sha256}
    finally:
        if media is not None:
            media.abort()
        site.close()
