"""Pinned Core/Lean and render integration for an unselected synthetic alley attempt."""
import hashlib
import importlib.util
import json
from pathlib import Path
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
from finalize_alley import finalize
from worker_exchange.runtime_cli import process,render
from worker_exchange.media import audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    root = Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-core-'))
    attempt = root/'attempt'
    saved.build(attempt)
    core.enrich(attempt)
    (attempt/'road.xodr').write_text(open_drive())
    manifest = json.loads((attempt/'capture/manifest.json').read_text())
    manifest['sources']['road.xodr'] = sha(attempt/'road.xodr')
    (attempt/'capture/manifest.json').write_text(json.dumps(manifest)+'\n')
    report = finalize(attempt,attempt/'analysis-report.json')
    converted = process(attempt,attempt/'converted',REPO/'runtime/pipeline/library',
        REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    config = json.loads((attempt/'config.json').read_text())
    rendered = render(attempt,attempt/'converted',config['case'])
    decoded = audit(rendered['video'],480,mapping_sha256=rendered['frame_map_sha256'],
                    receipt=attempt/'final-decode.json')
    summary = {'format':'c10052-alley-synthetic-core-integration-v1',
        'source_root':root.relative_to(REPO).as_posix(),
        'case_id':config['case_id'],'candidate_id':'primary',
        'analysis_report_sha256':sha(attempt/'analysis-report.json'),
        'road_sha256':sha(attempt/'road.xodr'),
        'converted':converted,'rendered_frames':rendered['frames'],
        'final_decode_passed':decoded['passed'],
        'selected':False,'accepted':False,
        'scope':'synthetic Core/Lean/video integration; no physical Native or statutory exception proof'}
    (HERE/'alley-core-summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    return summary


if __name__=='__main__':
    print(json.dumps(run(),indent=2,default=str))
