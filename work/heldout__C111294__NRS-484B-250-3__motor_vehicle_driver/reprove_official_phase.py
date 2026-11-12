"""Prove the retained red/green comparison and rejection of a changed binding."""

import json
from hashlib import sha256
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory

from official_phase_comparison_audit import audit


HERE = Path(__file__).resolve().parent


def attempt_from(receipt):
    parts = shlex.split(json.loads((HERE / receipt).read_text())['command'])
    return Path(parts[parts.index('--attempt') + 1])


def main():
    red = attempt_from('official-device-saved-proof.json')
    green = attempt_from('official-green-saved-proof.json')
    proof = audit(red, green)
    proof_path = HERE / 'official-phase-source-joined-proof.json'
    proof_path.write_text(json.dumps(proof, indent=2) + '\n')
    with TemporaryDirectory() as tmp:
        altered = Path(tmp)
        for source in green.iterdir():
            (altered / source.name).symlink_to(source, target_is_directory=source.is_dir())
        (altered / 'official_geometry_binding.json').unlink()
        (altered / 'official_geometry_binding.json').write_text('{}\n')
        try:
            audit(red, altered)
        except ValueError as exc:
            if 'binding is stale' not in str(exc):
                raise
            (HERE / 'official-phase-source-joined-negative.log').write_text(str(exc) + '\n')
        else:
            raise ValueError('Changed geometry binding passed phase comparison')
    print('phase comparison passed', sha256(proof_path.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
