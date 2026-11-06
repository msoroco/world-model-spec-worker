"""Check pinned saved processing reports absent source channels without acceptance."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit,run


def prove():
    positive=json.loads((HERE/'alley-saved-processing-summary.json').read_text())
    source=REPO/positive['source_root']
    root=Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-process-negative-'))
    attempt=root/'attempt';shutil.copytree(source/'attempt',attempt)
    for name in ('capture-seal.json','native-exit.json','acquisition-context.json'):
        (attempt/name).unlink(missing_ok=True)
    shutil.rmtree(attempt/'source_channels')
    seal_capture(attempt,frames=480,
        restoration={'restored':True,'synthetic_diagnostic':True},errors=[],
        encoder_exit_codes={name:0 for name in
            ('overview','approach','reference_corner','driver_reference')},
        context={'case_id':positive['case_id'],'synthetic_diagnostic':True,
                 'negative_missing_source_channels':True})
    record_native_exit(attempt)
    manifest=source/'package/draft-alley-execution-manifest.json'
    receipt=run(manifest,positive['case_id'],attempt,root/'processed',
        REPO/'runtime/pipeline/library',
        REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    version=Path(receipt['version'])
    log=(version/'analysis.log').read_text()
    if not receipt['missing_evidence'] or 'Missing required source: source_channels' not in log:
        raise ValueError('Missing source channel negative was not classified')
    result=json.loads((version/'analysis/result.json').read_text())
    if result.get('accepted') or receipt['physical_acceptance_claimed'] or receipt['legal_acceptance_claimed']:
        raise ValueError('Missing channel negative claimed acceptance')
    summary={'format':'c10052-alley-saved-processing-negative-v1',
        'source_root':root.relative_to(REPO).as_posix(),
        'case_id':positive['case_id'],'missing_evidence':True,
        'expected_error':'Missing required source: source_channels',
        'processing_version':receipt['version'],
        'selected':False,'accepted':False}
    (HERE/'alley-saved-processing-negative-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    print(json.dumps(prove(),indent=2))
