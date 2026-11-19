"""CPU acceptance protocol for exact C229126 diagnostic sources only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(ROOT / '.runtime-work/c229126-pipeline-output'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from delivery_audit import audit
from overtake_finalizer import analyze


def run(case_id, negative=False):
    manifest = HERE / 'execution-manifest.json'
    entries = [e for e in json.loads(manifest.read_text())['cases']
               if e['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unknown exact C229126 case')
    with TemporaryDirectory(prefix='c229126-acceptance-',
                            dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entries[0]['fixture_recipe'], base / 'fixture')
        make_attempt(manifest, case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        source = audit(base / 'attempt', case_id)
        analysis = analyze(base / 'attempt')
        observation = analysis['measurements']['overtake_sequence']['value']
        if (not source['source_checks_passed'] or
                observation['frame_count'] != source['frame_count'] or
                not observation['all_abreast_left']):
            raise ValueError('Original source and measured pass disagree')
        review = {name: {'source_sha256': detail['sha256'],
                         'reviewed_frames': detail['frames'],
                         'both_bodies_visible': True, 'roadway_visible': True}
                  for name, detail in source['camera_sources'].items()}
        if negative:
            review['approach']['source_sha256'] = 'stale diagnostic source'
        for name, detail in source['camera_sources'].items():
            selected = review[name]
            if (selected['source_sha256'] != detail['sha256'] or
                    selected['reviewed_frames'] != source['frame_count'] or
                    not selected['both_bodies_visible'] or
                    not selected['roadway_visible']):
                raise ValueError('Missing, stale, or failed original-pixel review: ' + name)
        print(json.dumps({'case_id': case_id, 'fixture_only': True,
                          'frame_count': source['frame_count'],
                          'four_source_decodes': sorted(review),
                          'physical_completion_verified': False,
                          'actual_pixel_visibility_verified': False,
                          'legal_acceptance_claimed': False}))


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def physical_run(case_id,kind):
 m=json.loads((HERE/'execution-manifest.json').read_text());entry=next(e for e in m['cases'] if e['case_id']==case_id)
 with TemporaryDirectory(prefix='c229126-physical-',dir=ROOT/'.runtime-work') as temp:
  base=Path(temp);make_fixture(ROOT,ROOT/entry['fixture_recipe'],base/'fixture');make_attempt(HERE/'execution-manifest.json',case_id,base/'attempt');copy_sources(base/'fixture',base/'attempt');attempt=base/'attempt';body=attempt/'participant_footprints.jsonl'
  original=analyze(attempt)['measurements']['overtake_sequence']['value'];expected_error=None
  if kind=='incomplete_motion':
   rows=[json.loads(s) for s in body.read_text().splitlines()];j=next(i for i,r in enumerate(rows) if r['frame']==original['first_return_frame']);hold=[point[1] for point in rows[j-1]['ego_corners']]
   for r in rows[j:]:
    for point,y in zip(r['ego_corners'],hold):point[1]=y
   body.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
   expected_error='Missing observed rightward return'
  if kind=='missing_evidence':body.unlink();expected_error='Missing required source: participant_footprints.jsonl'
  if expected_error:
   try:analyze(attempt)
   except ValueError as error:
    if expected_error not in str(error):raise
   else:raise AssertionError('Expected physical fixture rejection absent')
  else:assert original['all_abreast_left'] and original['first_return_frame'] is not None
  sources={name:digest(attempt/name) for name in ('trace.jsonl','video_frames.jsonl')}
  if body.is_file():sources['participant_footprints.jsonl']=digest(body)
  status={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
  return {'case_id':case_id,'fixture_kind':kind,'fixture_only':True,'diagnostic_fixture':True,'actual_native_capture':False,'physical_checks':{'maneuver':{'status':status,'method':'original source body overlap, same-direction left pass and first return; diagnostic rejection for incomplete/missing variants','sources':sources,'missing_evidence':[] if kind!='missing_evidence' else ['participant_footprints.jsonl']}},'maneuver_completed':kind=='complete_motion','realized_observables':{'abreast_frames':original['abreast_frames'],'first_return_frame':original['first_return_frame'],'minimum_gap_m':original['minimum_abreast_left_gap_m']} if kind=='complete_motion' else {},'provenance_kind':'synthetic_fixture','provenance_note':'Source-shaped CPU diagnostic; no actual Native motion or physical acceptance','physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def lifecycle_run(case_id):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if not any(entry['case_id'] == case_id for entry in manifest['cases']):
        raise ValueError('Unknown exact C229126 case')
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    def check(sequence):
        if sequence != events:
            raise ValueError('Saved processing preceded Native ownership closure')
    check(events)
    try:
        check(events[:-2] + events[-1:] + events[-2:-1])
    except ValueError:
        pass
    else:
        raise AssertionError('Early saved processing was accepted')
    print(json.dumps({'case_id': case_id, 'events': events,
                      'early_saved_processing_rejected': True,
                      'scope': 'synthetic CPU lifecycle protocol only'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion', 'missing_evidence'])
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    if args.kind:
        if args.negative or args.lifecycle or not args.output:
            parser.error('--kind requires --output and excludes --negative')
        result = physical_run(args.case, args.kind)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'case_id': args.case, 'kind': args.kind,
                          'status': result['physical_checks']['maneuver']['status']}))
    elif args.lifecycle:
        if args.negative or args.output:
            parser.error('--lifecycle excludes --negative and --output')
        lifecycle_run(args.case)
    else:
        run(args.case, args.negative)
