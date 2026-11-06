"""Probe an exact unselected alley bundle through pinned v1 package compatibility."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
saved_spec = importlib.util.spec_from_file_location('alley_saved',HERE/'prove-alley-saved.py')
saved = importlib.util.module_from_spec(saved_spec);saved_spec.loader.exec_module(saved)
core_spec = importlib.util.spec_from_file_location('core_fixture',HERE/'probe-core-synthetic.py')
core = importlib.util.module_from_spec(core_spec);core_spec.loader.exec_module(core)
from alley_geometry import open_drive
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env
import hashlib
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root):
    package = root/'package'
    package.mkdir()
    source = HERE/'draft-alley-execution-manifest.json'
    shutil.copyfile(source,package/source.name)
    shutil.copytree(HERE/'draft-alley-candidates',package/'draft-alley-candidates')
    config = json.loads((HERE/'native/alley-native-config.json').read_text())
    proposal = {'case_id':config['case_id'],'target_law_id':'NRS-484B-270-3',
        'target_type':'exact_clause','cell_id':'C10052','actor':'motor_vehicle_driver',
        'recording_description':config['recording_description'],
        'sweep_measurements':[],
        'comparison_variable':'alley_proximity_at_moving_facility_entry',
        'requested_setting':'near authored alley turn',
        'status':'unselected_synthetic_diagnostic'}
    (package/'proposals').mkdir()
    (package/'proposals/cases.json').write_text(json.dumps({'cases':[proposal]})+'\n')
    return package/source.name,config['case_id']


def fixture(root):
    source = root/'fixture'
    saved.build(source,full_resolution=True)
    core.enrich(source)
    (source/'road.xodr').write_text(open_drive())
    manifest = json.loads((source/'capture/manifest.json').read_text())
    manifest['sources']['road.xodr'] = sha(source/'road.xodr')
    (source/'capture/manifest.json').write_text(json.dumps(manifest)+'\n')
    (source/'config.json').unlink()
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', choices=('primary','fallback1','fallback2','fallback3'),
                        default='primary')
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-v1-'))
    manifest,case = prepare(root)
    source = fixture(root)
    output = root/'positive'
    receipt = run(manifest,case,source,output,REPO/'runtime/pipeline/library',
        REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
        args.candidate)
    negative = root/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    (negative/'alley-transition-sources.json').unlink()
    failure = subprocess.run([sys.executable,str(negative/'finalize_alley.py'),
        '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
        cwd=negative,env=execution_env(),text=True,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,timeout=300)
    (root/'negative.log').write_text(failure.stdout)
    if failure.returncode == 0 or 'alley-transition-sources.json' not in failure.stdout:
        raise ValueError('Exact alley missing-source negative did not reject')
    result = {'format':'c10052-alley-unselected-exact-v1-probe',
        'source_root':root.relative_to(REPO).as_posix(),
        'candidate_id':args.candidate,'manifest_sha256':sha(manifest),
        'construction_sha256':receipt['construction_sha256'],
        'fixture_sha256':receipt['fixture_sha256'],
        'positive_receipt_sha256':sha(output/'compatibility.json'),
        'negative_exit_code':failure.returncode,
        'negative_log_sha256':sha(root/'negative.log'),
        'selected':False,'accepted':False}
    (HERE/('alley-package-'+args.candidate+'-summary.json')).write_text(
        json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
