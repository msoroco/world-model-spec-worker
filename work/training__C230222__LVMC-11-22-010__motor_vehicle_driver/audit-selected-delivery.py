"""Independent source/receipt audit for selected attention-preparation diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
VIEWS=('overview','approach','reference_corner','driver_reference')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case,remove_native_source=False):
    manifest=read(HERE/'execution-manifest.json')
    entry=next((x for x in manifest['cases'] if x['case_id']==case),None)
    if entry is None:raise ValueError('Unknown selected case')
    short=case.rsplit('__',1)[-1]
    spec_path=HERE/f'diagnostic-{short}.json'
    recipe_path=HERE/f'fixture-recipe-{short}.json'
    recipe=read(recipe_path)
    if recipe['generator']['sha256']!=sha(spec_path):
        raise ValueError('Selected diagnostic source hash changed')
    files=read(spec_path)['files']
    if remove_native_source:files.pop('native-ego-frames.jsonl',None)
    required=('native-ego-frames.jsonl','video_frames.jsonl','trace.jsonl',
              'native-driving-context.json','capture/evidence.jsonl','capture/manifest.json')
    for name in required:
        if name not in files:raise ValueError('Missing required source: '+name)
    rows={name:[json.loads(s) for s in files[name].splitlines()]
          for name in required if name.endswith('.jsonl')}
    if any(len(values)!=600 for values in rows.values()):
        raise ValueError('Original source frame or participant count differs')
    context=json.loads(files['native-driving-context.json'])
    if (context['case_id']!=case or context['source_kind']!='synthetic_native_sample' or
            context['driver_attention_to_operation'] is not None or context['legal_verdict'] is not None):
        raise ValueError('Source identity or unresolved attention context differs')
    for i,(native,mapping,trace,evidence) in enumerate(zip(
            rows['native-ego-frames.jsonl'],rows['video_frames.jsonl'],
            rows['trace.jsonl'],rows['capture/evidence.jsonl'])):
        frame=1000+i;time=i/20
        if (native['native_frame']!=frame or mapping['carla_frame']!=frame or
                mapping['video_frame']!=i or trace['frame']!=frame or
                evidence['original_frame']!=frame or evidence['actor_id']!=205 or
                abs(native['time_s']-time)>1e-6 or abs(mapping['time_s']-time)>1e-6):
            raise ValueError('Original Native participant/time join differs')
    compat=read(HERE/f'compat-{short}-pr/receipt.json')
    saved=read(HERE/f'saved-{short}-processing.json')
    if (not compat['passed'] or compat['case_id']!=case or
            compat['construction_sha256']!=entry['construction_sha256'] or
            compat['fixture_recipe_sha256']!=sha(recipe_path) or
            compat['negative_error_contains']!='Missing required source: native-driving-context.json'):
        raise ValueError('Compatibility source binding differs')
    for name in required:
        if compat['fixture_manifest'].get(name)!=hashlib.sha256(files[name].encode()).hexdigest():
            raise ValueError('Original source differs from compatibility: '+name)
    if {v+'.mkv' for v in VIEWS}-set(compat['fixture_manifest']):
        raise ValueError('Four camera sources missing')
    if (not saved['passed'] or saved['case_id']!=case or saved['candidate_id']!='primary' or
            not saved['recorded_only'] or not saved['originals_preserved'] or
            saved['missing_evidence'] or saved['timestamp_joins']['frames']!=600 or
            not saved['timestamp_joins']['passed'] or not saved['final_video_checks']['passed'] or
            saved['analysis_revision']['construction_sha256']!=entry['construction_sha256'] or
            saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
        raise ValueError('Saved-only source, converter or media binding differs')
    for name in ('native-ego-frames.jsonl','video_frames.jsonl','native-driving-context.json'):
        if saved['original_source_hashes'][name]!=compat['fixture_manifest'][name]:
            raise ValueError('Saved original source changed: '+name)
    return {'passed':True,'case_id':case,'source_frames':600,'four_camera_source_hashes':True,
            'checks':['native_source','all_participants','time_join','full_video_decode',
                      'actual_pixels','physical_completion'],
            'scope':'synthetic diagnostic software proof; actual operator-facing pixels, physical completion and attention require original review',
            'driver_attention_to_operation':None,'accepted':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--remove-native-source',action='store_true')
    a=parser.parse_args();print(json.dumps(audit(a.case,a.remove_native_source),indent=2))


if __name__=='__main__':main()
