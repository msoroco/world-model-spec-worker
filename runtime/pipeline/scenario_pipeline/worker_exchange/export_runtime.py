"""Export exact pipeline code, observation library and optional small capture fixture."""
import argparse
import json
import shutil
from pathlib import Path
from .common import tree, write, sha


def fixture(source, destination, frames=3):
    source, destination=Path(source),Path(destination)
    destination.mkdir(parents=True)
    for name in ('road.xodr','config.json'):
        shutil.copyfile(source/name,destination/name)
    # Preserve every supplied per-frame observation stream, not a selected summary.
    for path in source.glob('*.jsonl'):
        with path.open() as stream:
            lines=[]
            for _ in range(frames):
                line=stream.readline()
                if not line:break
                lines.append(line)
        (destination/path.name).write_text(''.join(lines))
    for name in ('native_incoming_lane_topology.json','native_road_profile.json'):
        if (source/name).is_file():shutil.copyfile(source/name,destination/name)
    capture=destination/'capture';capture.mkdir()
    for name in ('recorder_info.txt','native_map_facts.json'):
        if (source/'capture'/name).is_file():shutil.copyfile(source/'capture'/name,capture/name)
    for relative in ('evidence.jsonl','native/frames.jsonl'):
        target=capture/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with (source/'capture'/relative).open() as stream:lines=[next(stream) for _ in range(frames)]
        target.write_text(''.join(lines))
        if relative.startswith('native/'):
            for row in map(json.loads,lines):
                for key in ('base','abstract'):
                    output=capture/'native'/row[key];output.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source/'capture/native'/row[key],output)
    manifest=json.loads((source/'capture/manifest.json').read_text())
    manifest.update(frames=frames,source_run='fixture:first-original-frames')
    manifest['sources']['trace.jsonl']=sha(destination/'trace.jsonl')
    write(capture/'manifest.json',manifest)
    import subprocess
    original=source/'overview.mkv'
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-threads','4','-i',str(original),
                    '-frames:v',str(frames),'-vf','scale=320:180','-c:v','ffv1',str(destination/'raw.mkv')],check=True)
    write(destination/'result.json',{'video_references':['raw.mkv']})
    write(destination/'case.json',{'case_id':'retained-speed-fixture','target_law_id':None})
    calibration=source/'environment_calibration.json'
    if calibration.exists():
        shutil.copyfile(calibration,destination/calibration.name)
        shutil.copyfile(source/'surface_provenance.json',destination/'surface_provenance.json')
        for sample in json.loads(calibration.read_text())['samples']:
            for key in ('rgb','instance'):
                relative=sample[key]['path'];target=destination/relative
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/relative,target)
        relocations={}
        for asset in json.loads((source/'surface_provenance.json').read_text())['source_assets']:
            relative='asset-snapshots/'+asset['sha256']+'/'+Path(asset['path']).name
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(asset['path'],target)
            relocations[asset['path']]=relative
        write(destination/'asset_relocations.json',{'surface_provenance_sha256':sha(source/'surface_provenance.json'),'paths':relocations})
    write(destination/'fixture-provenance.json',{'recording_id':source.parent.name,'frames':frames,
        'original_manifest_sha256':sha(source/'capture/manifest.json'),
        'original_trace_sha256':sha(source/'trace.jsonl'),
        'scope':'Diagnostic subset, not delivery. Camera resized for a small test; no visibility or maneuver acceptance.'})


def export(project,destination,fixture_attempt=None,capability_root=None):
    project=Path(project).resolve();destination=Path(destination)
    if destination.exists():raise ValueError('Use a fresh export directory')
    source=project/'scenario_pipeline';destination.mkdir(parents=True)
    for folder in ('traffic_spec_adapter','batch_pipeline','worker_exchange'):
        target=destination/'scenario_pipeline'/folder;target.mkdir(parents=True)
        for p in (source/folder).glob('*.py'):shutil.copyfile(p,target/p.name)
    for filename in ('authored_context.py','control_evidence.py','delivery_contract.py','expected_labels.py',
                     'review_recordings.py','trace_scope_audit.py','scenario_overlay.py','speed_overlay.py',
                     'workspaces.py','pipeline_paths.py','law_split.py','recording_store.py','convert_demo_videos.py','lane_signal_measurement.py'):
        shutil.copyfile(source/filename,destination/'scenario_pipeline'/filename)
    # Do not export bootstrap law corpora or local state merely to satisfy a directory layout.
    (destination/'scenario_pipeline/data').mkdir()
    shutil.copyfile(source/'data/canonical_parameter_aliases.json',destination/'scenario_pipeline/data/canonical_parameter_aliases.json')
    target=destination/'python';target.mkdir()
    for name in ('pipeline_capture.py','scene_graph_collector.py','original_observations.py'):shutil.copyfile(project/'scripts'/name,target/name)
    shutil.copytree(project/'third_party/carla_scene_graphs/carla_sgg',target/'carla_sgg',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    library=project/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'
    core=library/'TrafficSpec/Core';active=library/'splits/ACTIVE'
    full=library/'splits/full/TrafficSpec/Core' if active.exists() and active.read_text().strip()!='full' else core
    shutil.copytree(core,destination/'library/TrafficSpec/Core')
    shutil.copytree(full,destination/'library/TrafficSpec/Core',dirs_exist_ok=True)
    shutil.copyfile(library/'TrafficSpec/Core.lean',destination/'library/TrafficSpec/Core.lean')
    shutil.copyfile(library/'lean-toolchain',destination/'library/lean-toolchain')
    (destination/'ontology').mkdir()
    shutil.copyfile(library.parent/'ontology/ATOMS.md',destination/'ontology/ATOMS.md')
    (destination/'requirements-cpu.txt').write_text('numpy==1.24.4\nshapely==1.8.5.post1\nnetworkx==2.6.3\nPillow==10.4.0\ntqdm==4.67.1\nmatplotlib==3.7.5\npydot==2.0.0\n')
    if fixture_attempt:fixture(fixture_attempt,destination/'fixtures/retained-speed')
    tests=destination/'tests';tests.mkdir()
    for name in ('test_traffic_spec_adapter.py','test_original_participant_projection.py','test_native_control_observations.py',
                 'test_native_road_profile.py','test_control_portions.py','test_webm_export.py','test_lane_signal_measurement.py','test_full_footprint.py','test_optical_measurements.py','test_environment_relocation.py','test_runtime_handoff.py','test_native_output.py','test_world_restore.py','test_package_compatibility.py','test_worker_identity_preflight.py','test_worker_candidates.py','test_worker_delivery_handoff.py'):
        shutil.copyfile(source/'tests'/name,tests/name)
    capture_test=source/'tests/test_pipeline_capture.py'
    text=capture_test.read_text().replace("parents[2]/'scripts/","parents[1]/'python/")
    (tests/capture_test.name).write_text(text)
    write(tests/'source-locator-adaptation.json',{'test':capture_test.name,'original_sha256':sha(capture_test),'change':'Only fixture helper location scripts/ -> exported python/; assertions unchanged'})
    if capability_root:
        from .capability_catalogue import export as export_capabilities
        export_capabilities(project,capability_root,destination/'capabilities')
    files=tree(destination)
    write(destination/'SOURCE-MANIFEST.json',{'source':'main scenario_pipeline','files':files,
        'policy':'Exact Python copies, full observation Core only, no law registry, no state; host/SQLite operations local-only'})
    return files

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--destination',required=True);p.add_argument('--fixture-attempt');p.add_argument('--capability-root')
    a=p.parse_args();export(a.project,a.destination,a.fixture_attempt,a.capability_root)
