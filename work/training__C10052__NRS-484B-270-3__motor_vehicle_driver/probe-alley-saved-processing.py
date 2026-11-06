"""Exercise pinned saved processing on a sealed synthetic alley diagnostic."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('alley_package',HERE/'probe-alley-package-v1.py')
package = importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
from worker_exchange.package_compatibility import materialize_case
from worker_exchange.media import compose_four_views
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit,run


def main():
    root = Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-process-saved-'))
    manifest,case = package.prepare(root)
    fixture = package.fixture(root)
    attempt = root/'attempt'
    materialize_case(manifest,case,attempt,fixture,'primary')
    shutil.copytree(attempt/'channels',attempt/'source_channels')
    (attempt/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'physical_observation_claimed':False})+'\n')
    sources={name:attempt/(name+'.mkv') for name in
        ('overview','approach','reference_corner','driver_reference')}
    composed=compose_four_views(sources,attempt/'video_frames.jsonl',attempt/'raw.mkv')
    (attempt/'four-view-receipt.json').write_text(json.dumps(composed,indent=2)+'\n')
    seal_capture(attempt,frames=480,
        restoration={'restored':True,'synthetic_diagnostic':True},errors=[],
        encoder_exit_codes={name:0 for name in sources},
        context={'case_id':case,'synthetic_diagnostic':True})
    record_native_exit(attempt)
    print('scratch',root,flush=True)
    receipt=run(manifest,case,attempt,root/'processed',
        REPO/'runtime/pipeline/library',
        REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    if receipt['missing_evidence'] or not receipt['timestamp_joins']['passed']:
        raise ValueError('Pinned synthetic saved processing did not complete analysis')
    if not receipt['final_video_checks']['passed']:
        raise ValueError('Pinned synthetic saved processing final decode failed')
    result={'format':'c10052-alley-synthetic-saved-processing-proof-v1',
        'source_root':root.relative_to(REPO).as_posix(),
        'case_id':case,'processing_version':receipt['version'],
        'analysis_complete':True,'originals_preserved':receipt['originals_preserved'],
        'frames':receipt['timestamp_joins']['frames'],
        'final_video_passed':receipt['final_video_checks']['passed'],
        'selected':False,'physical_observation_claimed':False,'accepted':False}
    (HERE/'alley-saved-processing-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
