"""Controlled, source-backed CPU proof for each proposed fallback trigger."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from engineering import evaluate_trigger
from trigger_measure import measure

SOURCES=('interaction.json','native_samples.jsonl','camera_context.json')


def refresh(root):
    manifest_path=root/'capture/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for name in SOURCES:manifest['sources'][name]=fixture.sha(root/name)
    manifest_path.write_text(json.dumps(manifest,sort_keys=True)+'\n')


def mutate(root,kind):
    if kind=='fallback3':
        camera=json.loads((root/'camera_context.json').read_text())
        camera['pose']={'xyz_m':[0,0,200],'yaw_deg':0,'pitch_deg':-90}
        camera['fov_deg']=120
        (root/'camera_context.json').write_text(json.dumps(camera,sort_keys=True)+'\n')
    else:
        interaction=json.loads((root/'interaction.json').read_text())
        native=fixture.rows(root/'native_samples.jsonl') if hasattr(fixture,'rows') else [
            json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
        actor='bicycle' if kind=='fallback1' else 'motor_vehicle'
        shift=.55 if kind=='fallback1' else 8.
        key=actor+'_body_vertices_m'
        for row,sample in zip(interaction['frames'],native):
            target=row[actor]
            target['center_xy_m'][0]+=shift
            for vertex in target['body_xy_m']:vertex[0]+=shift
            sample[actor]=target
            for vertex in sample[key]:vertex[0]+=shift
        (root/'interaction.json').write_text(json.dumps(interaction,sort_keys=True)+'\n')
        fixture.write_rows(root/'native_samples.jsonl',native)
    refresh(root)


def check(root,candidate,expected):
    metrics=measure(root)
    path=root/'fallback-metrics.json'
    path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
    digest=fixture.sha(path)
    actual=evaluate_trigger(candidate,metrics,path,digest,diagnostic=True)
    if actual is not expected:raise AssertionError((candidate,expected,metrics))
    try:evaluate_trigger(candidate,metrics,path,digest)
    except ValueError as exc:
        if 'not bound to original' not in str(exc):raise
    else:raise AssertionError('Synthetic provenance accepted in production')
    try:evaluate_trigger(candidate,metrics,path,'0'*64,diagnostic=True)
    except ValueError as exc:
        if 'hash differs' not in str(exc):raise
    else:raise AssertionError('Wrong metric digest accepted')
    return metrics


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c111294-trigger-proof-') as temporary:
        root=Path(temporary)/'fixture'
        fixture.make(root,'witness_2',full_resolution=True)
        fixture.emulate_original_shape(root)
        originals={name:(root/name).read_bytes() for name in SOURCES}
        original_manifest=(root/'capture/manifest.json').read_bytes()
        baseline=measure(root)
        outcomes={}
        for candidate in ('fallback1','fallback2','fallback3'):
            for name,raw in originals.items():(root/name).write_bytes(raw)
            (root/'capture/manifest.json').write_bytes(original_manifest)
            before=check(root,candidate,candidate=='fallback3')
            mutate(root,candidate)
            after=check(root,candidate,candidate!='fallback3')
            outcomes[candidate]={'before':before['max_bicycle_route_cross_track_error_m' if candidate=='fallback1' else
                'min_motorist_conflict_clearance_s' if candidate=='fallback2' else 'min_projected_body_frame_margin_px'],
                'after':after['max_bicycle_route_cross_track_error_m' if candidate=='fallback1' else
                'min_motorist_conflict_clearance_s' if candidate=='fallback2' else 'min_projected_body_frame_margin_px'],
                'before_triggered':candidate=='fallback3','after_triggered':candidate!='fallback3'}
            (root/'camera_context.json').write_text('tampered')
            try:measure(root)
            except ValueError as exc:
                if 'hash absent or changed' not in str(exc):raise
            else:raise AssertionError('Altered camera source accepted')
        return {'passed':True,'source_kind':baseline['source_kind'],'cases':outcomes,
                'physical_behavior_observed':False,'original_pixels_verified':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
