"""End-to-end recorded-fixture proof for an exported runtime, CPU only."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .common import read,sha,write
from .runtime_cli import verify,process,render


def run(runtime,output,validator=None,lake=None,compare_to=None):
    runtime=Path(runtime).resolve();output=Path(output).resolve()
    verify(runtime)
    if output.exists():raise ValueError('Use a fresh verification output')
    output.mkdir(parents=True)
    if validator is None:
        if not lake:raise ValueError('Supply --lake to build decoder or --validator for an existing verified build')
        from traffic_spec_adapter.validate import build_validator
        validator=build_validator(runtime/'library',output/'decoder',lake)
    validator=Path(validator).resolve()
    attempt=output/'attempt';shutil.copytree(runtime/'fixtures/retained-speed',attempt)
    converted=output/'converted'
    process(attempt,converted,runtime/'library',validator)
    receipt=render(attempt,converted,read(attempt/'case.json'))
    from .media import audit
    original=audit(attempt/'raw.mkv',3,threads=4,receipt=output/'source-decode.json')
    primary=audit(receipt['video'],3,threads=4,receipt=output/'primary-decode.json')
    # Repeat work must adopt the exact-file receipt rather than decode again.
    cached=audit(attempt/'raw.mkv',3,threads=4,receipt=output/'source-decode.json')
    if cached!=original:raise ValueError('Receipt reuse changed')
    negatives=[]
    from traffic_spec_adapter.adapter import convert
    for label,change in [('bad_count',lambda m:m.update(frames=4)),('bad_source_hash',lambda m:m['sources'].update({'trace.jsonl':'0'*64}))]:
        broken=output/label;shutil.copytree(runtime/'fixtures/retained-speed',broken)
        manifest=read(broken/'capture/manifest.json');change(manifest);write(broken/'capture/manifest.json',manifest)
        try:convert(broken/'capture',broken,runtime/'library',output/(label+'-converted'))
        except ValueError as error:negatives.append({'fixture':label,'rejected':True,'reason':str(error)})
        else:raise ValueError('Corrupt fixture accepted: '+label)
    invalid=read(converted/'trace.json');invalid['scenes'][0]['subject']=999999999
    bad=output/'dangling-core.json';write(bad,invalid)
    p=subprocess.run([str(Path(validator).resolve()),str(bad),str(converted/'manifest.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    if not p.returncode:raise ValueError('Decoder accepted dangling identity')
    negatives.append({'fixture':'dangling_core_identity','rejected':True,'reason':p.stderr.strip()})
    env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(runtime/'scenario_pipeline'),str(runtime/'python')]),PYTHONDONTWRITEBYTECODE='1')
    with (output/'existing-regressions.log').open('w') as log:
        subprocess.run([sys.executable,'-m','unittest','discover','-s',str(runtime/'tests'),'-v'],cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    equivalent=None
    if compare_to:
        main=Path(compare_to).resolve();other=output/'main-converted'
        env['PYTHONPATH']=str(main)
        with (output/'main-equivalence.log').open('w') as log:
            subprocess.run([sys.executable,'-m','worker_exchange.runtime_cli','process','--attempt',str(attempt),
                            '--output',str(other),'--library',str(runtime/'library'),'--validator',str(validator)],
                           cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        equivalent={name:sha(other/name)==sha(converted/name) for name in ('trace.json','manifest.json','atom_contract.json')}
        if not all(equivalent.values()):raise ValueError('Main/export conversion mismatch')
    verify(runtime)
    result={'passed':True,'source_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),
            'frames':3,'decoder_validated':True,'mandatory_observation_coverage':True,'rendered_video_decoded':True,'source_decode_receipt_reused':True,
            'negative_fixtures':negatives,'main_equivalence':equivalent,
            'scope':'Retained diagnostic subset and software checks, not CARLA feasibility or delivery acceptance'}
    write(output/'verification.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--output',required=True)
    p.add_argument('--validator');p.add_argument('--lake');p.add_argument('--compare-to')
    a=p.parse_args();print(json.dumps(run(a.runtime,a.output,a.validator,a.lake,a.compare_to),indent=2))
