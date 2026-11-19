"""Locate the worker checkout from source and materialized Native bundles."""
from pathlib import Path


def repository_root(source):
    for parent in Path(source).resolve().parents:
        if (parent/'batch.json').is_file() and (parent/'runtime.py').is_file():
            return parent
    raise ValueError('Native bundle is outside a worker repository')
