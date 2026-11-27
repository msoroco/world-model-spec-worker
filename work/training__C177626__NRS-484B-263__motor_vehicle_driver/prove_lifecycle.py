"""CPU proof of Native seal, exit, release and immutable saved-source closure."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path('runtime/scenario_pipeline').resolve()))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import _closure, acknowledge_owner_release, record_native_exit


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError('Expected rejection: ' + phrase)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'attempt'
    root.mkdir()
    for name, content in (
        ('construction.json', '{}\n'), ('runner.py', '# synthetic\n'),
        ('trace.jsonl', '{"frame": 1}\n'),
        ('video_frames.jsonl', '{"video_frame": 0, "native_frame": 1, "time_s": 0}\n'),
        ('acquisition-provenance.json', '{"provenance_kind":"native","diagnostic_fixture":false}\n'),
    ):
        (root / name).write_text(content)
    reject(lambda: seal_capture(root, frames=1, restoration={'restored': False}, errors=[]),
           'verified restoration')
    seal = seal_capture(root, frames=1, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={'overview': 0, 'approach': 0,
                                            'reference_corner': 0, 'driver_reference': 0},
                        context={'case_id': 'synthetic_source'})
    assert seal['events'] == ['capture_finished', 'encoders_closed', 'restoration_verified']
    exit_receipt = record_native_exit(root)
    assert exit_receipt['event'] == 'native_exit'
    release = Path(tmp) / 'owner-release.json'
    reject(lambda: acknowledge_owner_release(root, release, False),
           'attest actual owner release')
    acknowledge_owner_release(root, release, True)
    _closure(root, release, 'native', False)
    (root / 'trace.jsonl').write_text('{"frame": 2}\n')
    reject(lambda: _closure(root, release, 'native', False), 'Sealed original changed')
print('PASS: Native seal/exit/release ordering, restoration and immutable-source negatives')
