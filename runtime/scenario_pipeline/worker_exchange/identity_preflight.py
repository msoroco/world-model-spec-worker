"""Reject copied law/cell identifiers in a selected Native construction."""
import ast
import re


_LAW = re.compile(r'-(\d{3})(?:-(\d+[a-z]?))?$')
_ROLE_LAW = re.compile(r'(?<!\d)(\d{3})[_-](\d+[a-z]?)(?!\d)', re.I)


def validate(construction, law_id, cell_id):
    files = {item['path']: item['content'] for item in construction.get('files', [])}
    expected = _LAW.search(law_id)
    if not expected:
        return {'law_id': law_id, 'cell_id': cell_id, 'identity_labels_checked': False,
                'reason': 'No canonical NRS numeric suffix in synthetic or external law ID'}
    if 'runner.py' in files:
        parsed = ast.parse(files['runner.py'])
        for node in ast.walk(parsed):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'set_attribute' and len(node.args) >= 2):
                continue
            key, value = node.args[:2]
            if not (isinstance(key, ast.Constant) and key.value == 'role_name'
                    and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            for label in _ROLE_LAW.finditer(value.value):
                if label.groups() != expected.groups():
                    raise ValueError('Native actor role_name carries another law: '+value.value)
    # An OpenDRIVE header may name the source cell of explicitly reused geometry;
    # it is provenance, not the active assignment identity.
    return {'law_id': law_id, 'cell_id': cell_id, 'identity_labels_checked': True}
