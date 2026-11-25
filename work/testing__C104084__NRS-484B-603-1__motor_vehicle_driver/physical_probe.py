"""CPU diagnostic of source-bound hill crest passage outcomes.

Inputs are explicitly synthetic fixture text. This proof checks the physical
event algorithm and never claims original CARLA motion or a legal conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crest_crossing import assess


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def probe(specification, kind):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unknown physical diagnostic outcome')
    specification = json.loads(Path(specification).read_text(encoding='utf-8'))
    files = specification['files']
    prefix = 'capture/crest-source/'
    manifest = json.loads(files[prefix + 'crest-manifest.json'])
    grade_text = files[prefix + 'grade.json']
    motion_text = files[prefix + 'motion.json']
    if _sha(grade_text) != manifest['grade_source']['sha256'] or \
            _sha(motion_text) != manifest['motion_source']['sha256']:
        raise ValueError('diagnostic source hash differs')
    grade = json.loads(grade_text)
    motion = json.loads(motion_text)
    if len(motion) != 900:
        raise ValueError('diagnostic motion needs full original frame count')
    if kind == 'incomplete_motion':
        crest = max(point['s_m'] for point in grade if point['z_m'] ==
                    max(p['z_m'] for p in grade))
        for row in motion:
            row['ego_s_m'] = min(row['ego_s_m'], crest - .5)
        motion_text = json.dumps(motion, separators=(',', ':')) + '\n'
    if kind == 'missing_evidence':
        motion_text = None
    sources = {'grade.json': _sha(grade_text),
               'frame-map.jsonl': _sha(files[prefix + 'frame-map.jsonl'])}
    if motion_text is not None:
        sources['motion.json'] = _sha(motion_text)
    evidence = None
    if kind != 'missing_evidence':
        try:
            evidence = assess(grade, motion, approach_start_m=manifest['approach_start_m'])
        except ValueError:
            evidence = None
    status = ('unverified' if kind == 'missing_evidence' else
              'met' if evidence is not None else 'not_met')
    result = {'format': 'c104084-physical-diagnostic', 'kind': kind,
              'case_id': manifest['case_id'],
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'maneuver_completed': status == 'met',
              'physical_checks': {'maneuver': {
                  'status': status,
                  'method': 'source-hashed original-shape grade and motion crest passage assessment',
                  'sources': sources,
                  'observed': evidence,
                  'legal_verdict_claimed': False}},
              'realized_observables': ({'crest_passage': {'value': evidence['crossing_station_m'],
                  'unit': 'm', 'method': 'observed station passage',
                  'source_sha256': sources['motion.json']}} if evidence else {}),
              'physical_acceptance_claimed': False}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('diagnostic physical outcome differs: ' + status)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = probe(args.spec, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': result['case_id'],
                      'kind': args.kind,
                      'status': result['physical_checks']['maneuver']['status']}))


if __name__ == '__main__':
    main()
