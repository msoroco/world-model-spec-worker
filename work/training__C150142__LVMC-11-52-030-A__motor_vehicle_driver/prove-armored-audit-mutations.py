"""Show independent armored draft audit rejects missing or falsified proofs."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('armored_audit', ROOT / 'audit-armored-drafts.py')
AUDIT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUDIT)


def main():
    originals = [json.loads((ROOT / name).read_text()) for name in (
        'update043-armored-offline-matrix.json',
        'update043-armored-source-matrix.json',
        'update043-armored-saved-matrix.json')]
    if AUDIT.audit(copy.deepcopy(originals))['candidate_proofs'] != 16:
        raise AssertionError('Unmodified armored matrix failed')
    mutations = (
        ('missing_candidate', lambda p: p[0]['candidates'].pop()),
        ('duplicate_source', lambda p: p[1]['records'].__setitem__(
            1, copy.deepcopy(p[1]['records'][0]))),
        ('missing_panel_negative', lambda p: p[1]['records'][0].__setitem__(
            'missing_panel_source_rejected', False)),
        ('missing_four_camera_decode', lambda p: p[2]['records'][0].__setitem__(
            'four_source_decodes', False)),
        ('invented_armored_identity', lambda p: p[2]['records'][0].__setitem__(
            'legal_armored_identity_verified', True)),
    )
    rejected = []
    for name, mutate in mutations:
        proofs = copy.deepcopy(originals)
        mutate(proofs)
        try:
            AUDIT.audit(proofs)
        except ValueError as exc:
            rejected.append({'mutation': name, 'rejected': True, 'reason': str(exc)})
        else:
            raise AssertionError('Armored audit accepted mutation: ' + name)
    target = ROOT / 'update043-armored-audit-mutations.json'
    target.write_text(json.dumps({'count': len(rejected), 'records': rejected},
                                 indent=2) + '\n')
    print(json.dumps({'count': len(rejected), 'all_rejected': True}))


if __name__ == '__main__':
    main()
