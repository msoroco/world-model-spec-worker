"""Independent original source, pixel-review and physical delivery audit.

A diagnostic route exercises the software join and always leaves acceptance
false. Production requires original reviewed source bytes and a human pixel
review bound to each fully decoded camera stream.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location('device_delivery_' + name, ROOT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


saved = module('saved_delivery')
review = module('site_review')
physical = module('physical_audit')
analysis = module('analysis')


class AuditError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise AuditError(reason)


def confined(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'Missing or escaped original source: ' + str(relative))
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_capture_seal(attempt: Path, case_id: str, manifest: dict, packet: dict) -> dict:
    """Bind the independently audited production sources to the closed Native capture."""
    attempt = Path(attempt).resolve()
    provenance_path = confined(attempt, 'acquisition-provenance.json')
    seal_path = confined(attempt, 'capture-seal.json')
    provenance = json.loads(provenance_path.read_text())
    require(provenance == {'provenance_kind': 'native', 'diagnostic_fixture': False,
                           'case_id': case_id, 'site_sha256': packet.get('site_sha256')},
            'original Native acquisition provenance missing or synthetic')
    seal = json.loads(seal_path.read_text())
    require(seal.get('events') == ['capture_finished', 'encoders_closed',
                                   'restoration_verified'],
            'original Native capture lifecycle seal incomplete')
    revision = seal.get('native_revision')
    require(revision == {'construction_sha256': sha(confined(attempt, 'construction.json')),
                         'runner_sha256': sha(confined(attempt, 'runner.py'))},
            'original Native construction or runner revision seal changed')
    sources = seal.get('sources')
    require(isinstance(sources, dict) and sources, 'original Native source inventory missing')
    required = {'device-native.json', 'saved-sources.json', 'trace.jsonl',
                'video_frames.jsonl', 'acquisition-provenance.json', 'capture/manifest.json'}
    required.add(manifest['native']['path'])
    required.update(ref['path'] for ref in manifest['media'].values())
    descriptor = manifest.get('reviewed_site', {})
    require(set(descriptor) == {'site_path', 'site_sha256', 'review_path', 'source_root'},
            'original reviewed source references missing from capture seal')
    required.update((descriptor['site_path'], descriptor['review_path']))
    review_packet = json.loads(confined(attempt, descriptor['review_path']).read_text())
    require(isinstance(review_packet.get('sources'), dict),
            'original reviewed source list missing')
    for ref in review_packet['sources'].values():
        require(isinstance(ref, dict) and isinstance(ref.get('path'), str),
                'original reviewed source path missing')
        required.add(str(Path(descriptor['source_root']) / ref['path']))
    require(required <= set(sources), 'original Native capture inventory omits a bound source')
    for relative, expected in sources.items():
        require(isinstance(relative, str) and Path(relative).as_posix() == relative and
                not Path(relative).is_absolute() and '..' not in Path(relative).parts and
                isinstance(expected, str) and len(expected) == 64,
                'invalid original Native sealed source reference')
        require(sha(confined(attempt, relative)) == expected,
                'original Native sealed source hash changed: ' + relative)
    require(sources[manifest['native']['path']] == manifest['native']['sha256'] and
            all(sources[ref['path']] == ref['sha256'] for ref in manifest['media'].values()) and
            sources['acquisition-provenance.json'] == sha(provenance_path) and
            descriptor['site_sha256'] == packet.get('site_sha256'),
            'original Native seal and saved source manifest disagree')
    try:
        _measurement, frames = analysis.measure_device_duty(attempt, case_id)
    except ValueError as error:
        raise AuditError('original Native 900-frame trace/video join failed: ' + str(error)) from error
    require(len(frames) == 900 and packet.get('diagnostic') is False,
            'original Native seal needs 900 non-diagnostic frames')
    return {'capture_seal_sha256': sha(seal_path),
            'acquisition_provenance_sha256': sha(provenance_path),
            'sealed_source_count': len(sources)}


def audit(attempt: Path, case_id: str, *, diagnostic: bool = False,
          profile: dict | None = None) -> dict:
    attempt = Path(attempt).resolve()
    source = saved.audit_complete(attempt, case_id=case_id, profile=profile,
                                  diagnostic_allowed=diagnostic)
    manifest = json.loads((attempt / 'saved-sources.json').read_text())
    native_path = confined(attempt, manifest['native']['path'])
    packet = json.loads(native_path.read_text())
    require(bool(packet.get('diagnostic')) == diagnostic, 'diagnostic/production source kind differs')
    receipt = {'format': 'worker-device-delivery-audit', 'case_id': case_id,
               'attempt_id': source['attempt_id'], 'recording_id': source['recording_id'],
               'native_sha256': sha(native_path), 'media_sha256': source['media_sha256'],
               'frame_count': source['frame_count'], 'native_source': True,
               'all_participants': True, 'time_join': True, 'full_video_decode': True,
               'actual_pixels': False, 'physical_completion': False,
               'diagnostic_fixture': diagnostic, 'legal_verdict_claimed': False}
    if diagnostic:
        receipt['scope'] = 'diagnostic source and full decode only'
        return receipt
    receipt.update(verify_capture_seal(attempt, case_id, manifest, packet))
    descriptor = manifest.get('reviewed_site', {})
    require(set(descriptor) == {'site_path', 'site_sha256', 'review_path', 'source_root'},
            'original site review references missing')
    site_path = confined(attempt, descriptor['site_path'])
    review_path = confined(attempt, descriptor['review_path'])
    source_root = (attempt / descriptor['source_root']).resolve()
    require(source_root.is_relative_to(attempt) and source_root.is_dir(),
            'original reviewed source root missing')
    verified = review.verify(site_path, descriptor['site_sha256'], case_id,
                             review_path, source_root)
    require(verified == packet.get('site_review_binding'),
            'saved original review binding stale')
    pixel_path = confined(attempt, manifest.get('pixel_review_path', ''))
    pixel = json.loads(pixel_path.read_text())
    require(pixel.get('case_id') == case_id and pixel.get('reviewer') and pixel.get('reviewed_at') and
            pixel.get('source_kind') == 'independent_original_pixel_review' and
            pixel.get('diagnostic_fixture') is False,
            'independent original pixel review missing')
    require(pixel.get('media_sha256') == source['media_sha256'], 'pixel review media hash stale')
    decoded = {name: row['decoded_frames_sha256'] for name, row in source['decoded_media'].items()}
    require(pixel.get('decoded_frames_sha256') == decoded,
            'pixel review decoded frame digest stale')
    seen = pixel.get('device_visible_original_frames')
    legible = pixel.get('device_legible_original_frames')
    frames = packet['frames']
    original = {row['frame'] for row in frames}
    require(isinstance(seen, list) and isinstance(legible, list) and
            len(seen) > 0 and len(legible) > 0 and
            set(legible) <= set(seen) <= original,
            'original device pixel visibility/legibility review missing')
    first_turn = next((row['frame'] for row in frames if row['ego'].get('u_turn_in_progress')), None)
    require(first_turn is None or min(legible) < first_turn,
            'original device pixels not legible before turn')
    require(pixel.get('governed_approach') == packet['device']['governed_approach'] and
            pixel.get('display_prohibits_u_turn') == packet['device']['prohibits_u_turn'],
            'pixel display does not match original Native device')
    physical_result = physical.assess(native_path, case_id)
    require(physical_result['physical_checks']['maneuver']['status'] == 'met',
            'independent original physical outcome incomplete')
    observed = physical_result['realized_observables']['observed_turn']
    receipt.update(actual_pixels=True, physical_completion=True,
                   site_review_sha256=sha(review_path), pixel_review_sha256=sha(pixel_path),
                   first_legible_frame=min(legible), first_turn_frame=first_turn,
                   observed_turn=observed,
                   realized_observables=physical_result['realized_observables'],
                   scope='source-bound independent engineering review; legal verdict unresolved')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.attempt, args.case, diagnostic=args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__':
    main()
