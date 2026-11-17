"""Immutable shared acquisition profiles; recordings contain hash-bound relative links."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def encoded(capability):
    return (json.dumps(capability,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()


def canonical_path(root):
    return Path(root)/'inputs/shared/manifest.json'


def link(root, directory, capability=None):
    root,directory=Path(root),Path(directory)
    canonical=canonical_path(root)
    if capability is not None:
        data=encoded(capability)
        if canonical.is_file() and canonical.read_bytes()!=data:
            checksum=hashlib.sha256(data).hexdigest()
            canonical=Path(root)/'inputs/shared/manifests'/(checksum+'.json')
        canonical.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=canonical.parent,prefix='.manifest-',delete=False)as stream:
                temporary=Path(stream.name);stream.write(data);stream.flush();os.fsync(stream.fileno())
            try:os.link(temporary,canonical)
            except FileExistsError:
                if canonical.read_bytes()!=data:
                    raise ValueError('Immutable acquisition profile changed')
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
    if not canonical.is_file():raise ValueError('Canonical acquisition manifest missing')
    destination=directory/'manifest.json'
    expected=os.path.relpath(canonical,directory)
    if destination.is_symlink() and os.readlink(destination)==expected:return
    if destination.exists() or destination.is_symlink():
        raise ValueError('Archive the existing manifest before replacing it: '+str(destination))
    destination.symlink_to(expected)


def verify(root, directory, expected_hash):
    path=Path(directory)/'manifest.json'
    target=canonical_path(root)
    profile=Path(root)/'inputs/shared/manifests'/(expected_hash+'.json')
    targets={target.resolve(),profile.resolve()}
    if (not path.is_symlink() or os.path.isabs(os.readlink(path)) or
            path.resolve() not in targets or not path.is_file() or
            hashlib.sha256(path.read_bytes()).hexdigest()!=expected_hash):
        raise ValueError('Final manifest hash differs: '+str(directory))


def link_sets(root):
    """Link existing non-held-out sets during fresh collection publication."""
    root=Path(root)
    if not canonical_path(root).is_file():return
    for name in ('demo-train','full-train','demo-test','full-test'):
        for parent in ('sets','work'):
            directory=root/parent/name
            if directory.is_dir():link(root,directory)
