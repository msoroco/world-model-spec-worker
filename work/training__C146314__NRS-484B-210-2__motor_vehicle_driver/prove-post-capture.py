"""CPU proof of exact saved-processing command and release dependency."""
import copy
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import post_capture
import runner

ROOT=Path(__file__).resolve().parent


def rejected(fn,label):
    try:fn()
    except (ValueError,FileNotFoundError):return label
    raise AssertionError('Post-capture command accepted '+label)


def prove():
    positives=[];negatives=[]
    manifest=runner.selected_manifest()
    with tempfile.TemporaryDirectory() as temporary:
        base=Path(temporary)
        for witness in ('reference','contrast'):
            case=ROOT.name+'__'+witness
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                attempt=base/(witness+'-'+candidate+'-attempt')
                output=base/(witness+'-'+candidate+'-saved')
                subprocess.run([str(runner.REPO/'.venv-cpu/bin/python'),
                    str(runner.REPO/'runtime.py'),'materialize',
                    '--manifest',str(manifest),'--case',case,
                    '--candidate',candidate,'--output',str(attempt)],
                    cwd=runner.REPO,check=True,capture_output=True)
                seal=attempt/'capture-seal.json'
                seal.write_text(json.dumps({'unit_mock':True})+'\n')
                native_exit=attempt/'native-exit.json'
                native_exit.write_text(json.dumps({'event':'native_exit',
                    'capture_seal_sha256':runner.sha(seal)})+'\n')
                owner=attempt/'operator-owner-release.json'
                receipt={'event':'owner_released','operator_attested':True,
                    'no_resource_operation_performed':True,
                    'native_construction_sha256':runner.sha(attempt/'construction.json'),
                    'native_exit_sha256':runner.sha(native_exit),
                    'unit_mock':True}
                owner.write_text(json.dumps(receipt)+'\n')
                args=(case,attempt,output,owner,
                      runner.REPO/'runtime/pipeline/library',base/'validator')
                planned=post_capture.command(*args,manifest=manifest)
                assert planned[planned.index('--case')+1]==case
                assert planned[planned.index('--owner-release-receipt')+1]==str(owner)
                positives.append((witness,candidate))
                if witness=='reference' and candidate=='primary':
                    owner.unlink()
                    negatives.append(rejected(lambda:post_capture.command(
                        *args,manifest=manifest),'missing-operator-release'))
                    owner.write_text(json.dumps({**receipt,
                        'native_exit_sha256':'0'*64})+'\n')
                    negatives.append(rejected(lambda:post_capture.command(
                        *args,manifest=manifest),'wrong-native-exit'))
                    owner.write_text(json.dumps({**receipt,
                        'operator_attested':False})+'\n')
                    negatives.append(rejected(lambda:post_capture.command(
                        *args,manifest=manifest),'unattested-owner-release'))
                    owner.write_text(json.dumps(receipt)+'\n')
                    negatives.append(rejected(lambda:post_capture.command(
                        case,attempt,attempt/'derived',owner,args[4],args[5],manifest),
                        'derived-inside-original'))
                    calls=[]
                    def fake_run(command,**kwargs):
                        calls.append(command)
                        version=output/'v0001';version.mkdir(parents=True)
                        (version/'processing.json').write_text(json.dumps({
                            'case_id':case,'candidate_id':candidate,
                            'passed':True,'recorded_only':True,
                            'originals_preserved':True,'missing_evidence':False,
                            'events':['saved_processing_started',
                                      'selected_analysis_executed',
                                      'originals_verified']})+'\n')
                    with patch.object(post_capture.subprocess,'run',fake_run):
                        processed=post_capture.execute(*args,manifest=manifest)
                    assert len(calls)==1 and processed['events'][0]=='saved_processing_started'
                    with patch.object(post_capture.subprocess,'run',lambda *a,**k:None):
                        negatives.append(rejected(lambda:post_capture.execute(
                            *args,manifest=manifest),'stale-previous-processing-receipt'))
    return {'format':'c146314-post-capture-cpu-contract-v1','passed':True,
            'exact_candidate_commands':len(positives),
            'negative_rejections':negatives,
            'mock_saved_processing_start_checked':True,
            'operator_owner_release_actually_attested':False,
            'original_carla_executed':False,
            'physical_acceptance_claimed':False}


if __name__=='__main__':print(json.dumps(prove(),sort_keys=True))
