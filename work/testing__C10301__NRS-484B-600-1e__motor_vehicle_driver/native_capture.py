"""Exact-case Native acquisition, preserving original site, speed and media."""
from __future__ import annotations

from pathlib import Path
import json
import hashlib
import shutil

from capture_finalizer import finalize_capture
from native_media import NativeMedia
from native_motion import capture_speed
from native_motion import CASE_PREFIX, TARGETS
from native_site import construct


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def capture(world, packet_path: Path, attempt: Path, case_id: str,
            native_run_id: str, uncertainty_mps: float, transform_factory,
            control_factory, *, diagnostic_fixture=False,
            media_factory=NativeMedia, graph_reader=None, client=None):
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
    recorder_started = False
    try:
        attempt = Path(attempt)
        attempt.mkdir(parents=True, exist_ok=True)
        site_source = attempt / 'native-site-source.json'
        source_bytes = Path(packet_path).read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != site.packet_sha256:
            raise ValueError('Native site packet changed after construction')
        with site_source.open('xb') as stream:
            stream.write(source_bytes)
        road_bytes = world.get_map().to_opendrive().encode('utf-8')
        if hashlib.sha256(road_bytes).hexdigest() != packet['opendrive_sha256']:
            raise ValueError('original Native OpenDRIVE source changed')
        with (attempt / 'road.xodr').open('xb') as stream:
            stream.write(road_bytes)
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
        recorder_path = attempt / 'carla_recorder.log'
        if not diagnostic_fixture:
            if client is None:
                raise ValueError('original Native CARLA client required for recorder')
            if recorder_path.exists() or client.start_recorder(str(recorder_path), True) is False:
                raise ValueError('original Native recorder refused to start')
            recorder_started = True
        if graph_reader is None and not diagnostic_fixture:
            from original_graph import collect
            def graph_reader(world, actor, snapshot, frame, time_s,
                             observed_packet):
                return collect(world, actor, snapshot,
                               expected_frame=frame,
                               expected_time_s=snapshot.timestamp.elapsed_seconds,
                               recording_time_s=time_s,
                               observed_evidence=observed_packet)
        motion = capture_speed(world, site.actor, control_factory, attempt,
                               case_id, native_run_id, uncertainty_mps,
                               diagnostic_fixture=diagnostic_fixture,
                               camera_frame_reader=media.read,
                               route_reader=site.observe_route,
                               graph_reader=graph_reader)
        frames, paths = media.finish()
        if recorder_started:
            client.stop_recorder()
            recorder_started = False
            if not recorder_path.is_file() or not recorder_path.stat().st_size:
                raise ValueError('original Native recorder source missing')
            info = client.show_recorder_file_info(str(recorder_path), False)
            if (not isinstance(info, str) or
                    f'Create {site.actor.id}: ' not in info):
                raise ValueError('original Native recorder subject census missing')
            with (attempt / 'recorder_info.txt').open('x', encoding='utf-8') as stream:
                stream.write(info)
        index = finalize_capture(attempt, case_id, frames, paths,
                                 site_source=site_source)
        aliases = {'overview': 'front', 'approach': 'front_left',
                   'reference_corner': 'front_right',
                   'driver_reference': 'rear'}
        for name, camera in aliases.items():
            target = attempt / (name + '.mkv')
            if target.exists():
                raise ValueError('runtime camera media alias already exists')
            shutil.copyfile(paths[camera], target)
            if _sha_file(target) != index['cameras'][camera]['sha256']:
                raise ValueError('runtime camera media alias differs from original')
        return {'motion': motion, 'capture_index': index,
                'site_packet_sha256': site.packet_sha256}
    finally:
        if recorder_started:
            client.stop_recorder()
        if media is not None:
            media.abort()
        site.close()
