"""Exercise pinned four-view composition and sealing on a diagnostic fixture."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.media import compose_four_views
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, _closure
from worker_exchange.runtime_cli import execution_env


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    log = HERE / 'package-compatibility-controlled_1.log'
    first = log.read_text().splitlines()[0]
    if not first.startswith('scratch '):
        raise ValueError('No exact package fixture')
    scratch = Path(first[8:])
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('Diagnostic fixture is outside ignored local scratch')
    source = scratch / 'fixture'
    output = scratch / 'output'
    if not source.is_dir() or not output.is_dir():
        raise ValueError('Exact package fixture missing')
    with tempfile.TemporaryDirectory(prefix='c329610-2a-closure-', dir=ROOT/'.runtime-work') as temp:
        attempt = Path(temp) / 'attempt'
        shutil.copytree(source, attempt)
        for name in ('construction.json','runner.py','config.json'):
            shutil.copy2(output/name, attempt/name)
        shutil.copytree(attempt/'channels', attempt/'source_channels')
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'diagnostic_fixture': True,
            'source_kind': 'synthetic_software_fixture',
            'native_executed': False})+'\n')
        names = ('overview','approach','reference_corner','driver_reference')
        sources = {name: attempt/(name+'.mkv') for name in names}
        receipt = compose_four_views(sources,attempt/'video_frames.jsonl',attempt/'raw.mkv')
        (attempt/'four-view-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        restoration = {'restored':True,'scope':'synthetic mock; no CARLA world'}
        seal = seal_capture(attempt,frames=480,restoration=restoration,errors=[],
                            encoder_exit_codes={name:0 for name in names},
                            context={'diagnostic_fixture':True,'native_executed':False})
        assert seal['diagnostic_fixture'] is True
        assert seal['frames']==480 and receipt['frames']==480
        record_native_exit(attempt)
        _closure(attempt,None,'diagnostic',True)
        finalized = subprocess.run([sys.executable, str(HERE/'native/finalize.py'),
            '--attempt', str(attempt), '--output', str(attempt/'analysis-report.json')],
            env=execution_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=180)
        if finalized.returncode:
            raise ValueError('Sealed diagnostic finalization failed: '+finalized.stdout)
        analysis = json.loads((attempt/'analysis-report.json').read_text())
        result = json.loads((attempt/'result.json').read_text())
        assert analysis['acquisition_provenance']['diagnostic_fixture'] is True
        assert analysis['acquisition_provenance']['native_executed'] is False
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert not any(result[key] for key in ('setup_confirmed','behavior_attempted',
                                               'maneuver_completed','accepted','legal_verdict_claimed'))
        with (attempt/'native_samples.jsonl').open('a') as stream:
            stream.write('changed\n')
        try:
            _closure(attempt,None,'diagnostic',True)
        except ValueError as error:
            assert 'Sealed original changed: native_samples.jsonl' in str(error)
        else:
            raise AssertionError('Changed sealed Native source accepted')
        sys.path.insert(0, str(HERE/'native'))
        from finalize import capture_provenance
        try:
            capture_provenance(attempt,480)
        except ValueError as error:
            assert 'Sealed original changed: native_samples.jsonl' in str(error)
        else:
            raise AssertionError('Changed sealed source acquired Native finalizer provenance')
        print(json.dumps({'passed':True,'diagnostic_fixture':True,'native_executed':False,
                          'frames':480,'four_view_receipt_sha256':sha(attempt/'four-view-receipt.json'),
                          'capture_seal_sha256':sha(attempt/'capture-seal.json'),
                          'positive_closure_and_changed_source_negative':True,
                          'sealed_diagnostic_finalization_without_native_claim':True,
                          'finalizer_changed_sealed_source_rejected':True,
                          'scope':'synthetic CPU closure only; no CARLA, physical or accepted recording'}))


if __name__ == '__main__':
    main()
