"""Run every exact unselected C104538 candidate on case-specific synthetic CPU sources."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location('c104538_joined_probe', HERE / 'probe-joined-package.py')
joined = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joined)
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def main():
    root = REPO / '.runtime-work/c104538/joined-package-matrix-v6'
    if root.exists():
        raise ValueError('Retain prior joined package matrix')
    root.mkdir(parents=True)
    manifest = HERE / 'draft-execution-manifest.json'
    library = REPO / 'runtime/pipeline/library'
    validator = REPO / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'
    summary = {'format': 'c104538-unselected-synthetic-v1-package-matrix',
        'selected': False, 'accepted': False, 'cases': []}
    environment = execution_env()
    environment['PATH'] = str(REPO / '.runtime-work/linux_arm64') + os.pathsep + environment.get('PATH', '')
    environment['LD_LIBRARY_PATH'] = str(REPO / '.runtime-work/geos-wheel/shapely.libs')
    for suffix in ('below_500_ft', 'at_500_ft', 'above_500_ft'):
        folder = root / suffix
        folder.mkdir()
        case_id = HERE.name + '__' + suffix
        case = {'case_id': case_id, 'suffix': suffix, 'candidates': []}
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            fixture = folder / (candidate + '-fixture')
            joined.build(fixture, suffix)
            context_path = fixture / 'native-construction-context.json'
            context = json.loads(context_path.read_text())
            context['candidate_id'] = candidate
            joined.write(context_path, context)
            output = folder / candidate
            receipt = run(manifest,case_id,fixture,output,library,validator,candidate)
            negative = folder / (candidate + '-negative')
            materialize_case(manifest,case_id,negative,fixture,candidate)
            (negative / 'native_body_history.jsonl').unlink()
            failed = subprocess.run([sys.executable,str(negative / 'finalize.py'), '--attempt',
                str(negative), '--output',str(negative / 'analysis-report.json')],
                cwd=negative,env=environment,text=True,capture_output=True,timeout=300)
            negative_log = folder / (candidate + '-negative.log')
            negative_log.write_text(failed.stdout + failed.stderr)
            if failed.returncode == 0 or 'native_body_history.jsonl' not in failed.stderr:
                raise ValueError('Exact case-source negative did not reject: '+case_id+' '+candidate)
            changed = folder / (candidate + '-changed-obstruction')
            materialize_case(manifest,case_id,changed,fixture,candidate)
            authored_path = changed / 'obstruction.json'
            authored_path.write_bytes(authored_path.read_bytes() + b' ')
            changed_run = subprocess.run([sys.executable,str(changed / 'finalize.py'), '--attempt',
                str(changed), '--output',str(changed / 'analysis-report.json')],
                cwd=changed,env=environment,text=True,capture_output=True,timeout=300)
            changed_log = folder / (candidate + '-changed-obstruction.log')
            changed_log.write_text(changed_run.stdout + changed_run.stderr)
            if changed_run.returncode == 0 or 'Authored obstruction source hash differs' not in changed_run.stderr:
                raise ValueError('Changed authored obstruction source did not reject: '+case_id+' '+candidate)
            changed_road = folder / (candidate + '-changed-road')
            materialize_case(manifest,case_id,changed_road,fixture,candidate)
            road_path = changed_road / 'authored_road.xodr'
            road_path.write_bytes(road_path.read_bytes() + b' ')
            road_run = subprocess.run([sys.executable,str(changed_road / 'finalize.py'), '--attempt',
                str(changed_road), '--output',str(changed_road / 'analysis-report.json')],
                cwd=changed_road,env=environment,text=True,capture_output=True,timeout=300)
            road_log = folder / (candidate + '-changed-road.log')
            road_log.write_text(road_run.stdout + road_run.stderr)
            if road_run.returncode == 0 or 'Authored road source hash differs' not in road_run.stderr:
                raise ValueError('Changed authored road source did not reject: '+case_id+' '+candidate)
            case['candidates'].append({'candidate_id': candidate,
                'fixture_trace_sha256': joined.sha(fixture / 'trace.jsonl'),
                'fixture_road_sha256': joined.sha(fixture / 'road.xodr'),
                'positive': receipt, 'positive_receipt_sha256': joined.sha(output / 'compatibility.json'),
                'negative_exit_code': failed.returncode,
                'negative_removed': 'native_body_history.jsonl',
                'negative_log_sha256': joined.sha(negative_log),
                'changed_obstruction_exit_code': changed_run.returncode,
                'changed_obstruction_log_sha256': joined.sha(changed_log),
                'changed_road_exit_code': road_run.returncode,
                'changed_road_log_sha256': joined.sha(road_log)})
            print(json.dumps({'case_id':case_id,'candidate_id':candidate,'positive':True,
                              'negative_rejected':True}),flush=True)
        summary['cases'].append(case)
    joined.write(HERE / 'joined-package-matrix-summary.json', summary)
    print(json.dumps({'passed': True,'cases':len(summary['cases']),
                      'candidates':sum(len(case['candidates']) for case in summary['cases'])}))


if __name__ == '__main__':
    main()
