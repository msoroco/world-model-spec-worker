"""Run all 24 exact unselected rider bundles through synthetic v1 packages."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env

spec=importlib.util.spec_from_file_location('rider_probe',HERE/'prove-rider-packages-v1.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    root=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10052-rider-matrix-'))
    manifest=probe.prepare(root)
    summary={'format':'c10052-rider-exact-package-matrix-v1','manifest_sha256':sha(probe.MANIFEST),
        'root':root.relative_to(ROOT).as_posix(),'results':[],
        'selected':False,'accepted':False,'original_native_capture_executed':False}
    summary_path=HERE/'rider-package-matrix-summary.json'
    for rider_type in ('bicycle','electric_bicycle','electric_scooter'):
        for response in ('clear','conflict'):
            case=HERE.name+'__rider_'+rider_type+'_'+response
            pair_root=root/(rider_type+'-'+response);pair_root.mkdir()
            source=probe.fixture(pair_root,rider_type,response)
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                key=rider_type+'-'+response+'-'+candidate
                output=root/(key+'-positive')
                receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
                    ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',candidate)
                report=json.loads((output/'analysis-report.json').read_text())
                result=json.loads((output/'result.json').read_text())
                metric=report['measurements']['rider_conflict_observation']['value']
                assert metric['ego_entered_after_rider_cleared']==(response=='clear')
                assert result['accepted'] is False and receipt['passed'] is True
                negative=root/(key+'-negative')
                materialize_case(manifest,case,negative,source,candidate)
                with (negative/'rider_native_samples.jsonl').open('a') as stream:stream.write(' ')
                command=[sys.executable,str(negative/'finalize_rider.py'),
                    '--attempt',str(negative),'--output',str(negative/'analysis-report.json')]
                failed=subprocess.run(command,cwd=negative,env=execution_env(),text=True,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
                log=root/(key+'-negative.log');log.write_text(failed.stdout)
                assert failed.returncode!=0 and 'Changed original source bytes' in failed.stdout
                assert not (negative/'result.json').exists()
                item={'case_id':case,'candidate_id':candidate,
                    'construction_sha256':receipt['construction_sha256'],
                    'fixture':source.relative_to(ROOT).as_posix(),
                    'fixture_rider_rows_sha256':sha(source/'rider_native_samples.jsonl'),
                    'positive':output.relative_to(ROOT).as_posix(),
                    'positive_receipt_sha256':sha(output/'compatibility.json'),
                    'analysis_report_sha256':sha(output/'analysis-report.json'),
                    'result_sha256':sha(output/'result.json'),
                    'negative_log':log.relative_to(ROOT).as_posix(),
                    'negative_log_sha256':sha(log),
                    'first_ego_frame':metric['first_ego_frame'],
                    'last_rider_frame':metric['last_rider_frame'],
                    'simultaneous_conflict_frames':metric['simultaneous_conflict_frames'],
                    'source_scope':report['source_scope']}
                summary['results'].append(item)
                summary['passed']=len(summary['results'])==24
                write(summary_path,summary)
                print(key,'passed',flush=True)
    assert summary['passed']
    print(json.dumps({'passed':True,'cases':6,'candidates':24,
                      'summary_sha256':sha(summary_path)},indent=2))


if __name__=='__main__':main()
