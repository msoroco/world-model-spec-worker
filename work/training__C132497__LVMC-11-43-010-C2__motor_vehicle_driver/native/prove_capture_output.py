"""CPU proof of runtime materialized-attempt capture output handling."""
import hashlib
import json
import tempfile
from pathlib import Path

from capture import prepare_output


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(bundle, output, expected):
    try:prepare_output(bundle,output)
    except ValueError as error:
        if expected not in str(error):raise
    else:raise ValueError('Unsafe capture output was accepted')


with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    source=root/'materialized';source.mkdir()
    (source/'controller-intention.json').write_text(json.dumps({'turn_direction':'right'})+'\n')
    (source/'config.json').write_text(json.dumps({
        'controller_intention_sha256':sha(source/'controller-intention.json')})+'\n')
    a,b=prepare_output(source,source)
    assert a==b==source.resolve()
    (source/'native-raw-actors.jsonl').write_text('')
    reject(source,source,'fresh attempt')
    (source/'native-raw-actors.jsonl').unlink()
    separate=root/'separate'
    prepare_output(source,separate)
    assert sha(separate/'controller-intention.json')==sha(source/'controller-intention.json')
    reject(source,separate,'fresh attempt')
    (source/'config.json').write_text(json.dumps({'controller_intention_sha256':'0'*64})+'\n')
    reject(source,source,'intention changed')
print(json.dumps({'passed':True,'materialized_attempt':True,'fresh_separate_output':True,
                  'negative_rejections':3}))
