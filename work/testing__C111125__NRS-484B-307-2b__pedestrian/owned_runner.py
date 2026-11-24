"""Operator-owned Native crossing entrypoint with reviewed source binding.

The caller owns world settings and camera sensors. Capture never substitutes a
diagnostic site for the original intersection or claims legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import capture
from native_crossing import source, spawn_pedestrian, verify_site
from pedestrian_control import ENTER_CASES, WAIT_CASES


def capture_reviewed(session, site_path, case_id, output_dir, *, publisher=None,
                     camera_dimensions=None):
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in ENTER_CASES | WAIT_CASES or not case_id.startswith(
            'testing__C111125__NRS-484B-307-2b__pedestrian__'):
        raise ValueError('unknown exact pedestrian case')
    site_path = Path(site_path).resolve(strict=True)
    site_bytes = site_path.read_bytes()
    site = json.loads(site_bytes)
    if (site.get('diagnostic_fixture') is not False or
            site.get('reviewed_original_site') is not True or
            not site.get('review_source_id')):
        raise ValueError('reviewed original pedestrian site packet required')
    verify_site(site, site_path.parent)
    output_dir = Path(output_dir).resolve()
    if not (output_dir / 'config.json').is_file() or not (output_dir / 'construction.json').is_file():
        raise ValueError('materialized exact construction required')
    config = json.loads((output_dir / 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('materialized construction selected another case')
    if any((output_dir / name).exists() for name in
           ('capture-receipt.json', 'original-frames.json', 'site-source.json')):
        raise ValueError('original capture already exists')
    actor = None
    try:
        actor = spawn_pedestrian(session.world, site, site_path.parent,
                                 session.blueprint_library, session.transform_factory)
        frame_sink = getattr(session, 'frame_sink', None)
        if frame_sink is None:
            if getattr(session, 'client', None) is None:
                raise ValueError('original CARLA client required for pedestrian graph capture')
            from pedestrian_graph_sink import PedestrianGraphSink
            frame_sink = PedestrianGraphSink(session.client, actor, output_dir, case_id)
        receipt = capture(session.world, actor, site, site_path.parent, suffix,
                          session.head_reader, session.device_reader,
                          session.control_factory, session.vector_factory,
                          output_dir, ticks=899,
                          camera_readers=session.camera_readers,
                          camera_dimensions=camera_dimensions,
                          frame_sink=frame_sink)
        for ref in site['original_sources']:
            original = source(ref, site_path.parent)
            target = (output_dir / ref['path']).resolve()
            if not target.is_relative_to(output_dir) or target.exists():
                raise ValueError('original site source destination differs')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        (output_dir / 'site-source.json').write_bytes(site_bytes)
        receipt['reviewed_site_source'] = {
            'path': 'site-source.json',
            'sha256': hashlib.sha256(site_bytes).hexdigest(),
            'review_source_id': site['review_source_id'],
        }
        (output_dir / 'capture-receipt.json').write_text(
            json.dumps(receipt, indent=2) + '\n')
        if publisher is None:
            from native_publication import publish_original
            publisher = publish_original
        try:
            receipt['runtime_publication'] = publisher(output_dir, case_id)
        except Exception as error:
            (output_dir / 'native-run-status.json').write_text(json.dumps({
                'case_id': case_id, 'capture_complete': True,
                'publication_complete': False,
                'errors': [str(error)],
                'physical_acceptance_claimed': False}, indent=2) + '\n')
            raise
        return receipt
    finally:
        if actor is not None:
            actor.destroy()


def seal_after_restoration(output_dir, restoration):
    """Seal only after the session owner reports actual world restoration."""
    from worker_exchange.native_output import seal_capture
    root = Path(output_dir).resolve()
    if (not isinstance(restoration, dict) or
            restoration.get('restored') is not True or
            not restoration.get('source')):
        raise ValueError('original operator restoration receipt required')
    receipt = json.loads((root / 'capture-receipt.json').read_text())
    published = json.loads((root / 'result.json').read_text())
    if receipt['case_id'] != published['case_id'] or receipt['frame_count'] != 900:
        raise ValueError('published pedestrian capture differs from original')
    return seal_capture(root, frames=900, restoration=restoration, errors=[],
                        encoder_exit_codes={name: 0 for name in
                                            ('overview', 'approach',
                                             'reference_corner', 'driver_reference')})
