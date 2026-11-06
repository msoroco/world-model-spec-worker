"""Independent hash and one-variable comparison audit for exception fixtures."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proof=json.loads((HERE/'exception-fixture-proof.json').read_text())
    if proof['passed'] is not True or len(proof['rows'])!=3:
        raise ValueError('Three controlled source branches required')
    for row in proof['rows']:
        folder=HERE/'exception-fixtures'/row['branch']
        good=folder/'positive.json';bad=folder/'negative.json'
        if sha(good)!=row['positive_sha256'] or sha(bad)!=row['negative_sha256']:
            raise ValueError('Exception source hash changed')
        p=json.loads(good.read_text());n=json.loads(bad.read_text())
        changed={k for k in p|n if p.get(k)!=n.get(k)}
        if changed!={row['changed_source_field']}:
            raise ValueError('Exception source pair changed more than one field')
        if p['branch']!=n['branch'] or p['synthetic_fixture'] is not True or n['synthetic_fixture'] is not True:
            raise ValueError('Source pair identity or synthetic scope differs')
    print(json.dumps({'passed':True,'source_pairs':3,'one_field_changed_per_pair':True,
                      'scope':'source completeness diagnostic only; no physical or legal conclusion'}))


if __name__=='__main__':main()
