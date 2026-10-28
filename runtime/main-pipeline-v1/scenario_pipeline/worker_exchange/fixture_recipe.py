"""Regenerate small case fixtures from one pinned shared capture and text inputs."""
import json
import shutil
from pathlib import Path
from .common import digest, read, sha, tree, within


def inspect(repo, recipe_path):
    repo=Path(repo).resolve();recipe_path=Path(recipe_path).resolve()
    if repo not in recipe_path.parents:raise ValueError('Fixture recipe must be in worker repository')
    recipe=read(recipe_path)
    if recipe.get('format')!='worker-fixture-recipe-v1':raise ValueError('Unknown fixture recipe')
    base=within(repo,recipe.get('base',''))
    if not base.is_dir() or not str(base.relative_to(repo)).startswith('runtime/'):
        raise ValueError('Fixture base must be pinned runtime data')
    additions=recipe.get('additions')
    if not isinstance(additions,list) or not additions:
        raise ValueError('Case fixture needs source-specific text additions')
    seen=set();sources={};base_files=set(tree(base))
    removed=recipe.get('remove',[])
    if removed!=['case.json','config.json','result.json']:
        raise ValueError('Fixture recipe must remove only the retained example case/config/result')
    for item in additions:
        target=item.get('path');source=item.get('source')
        if not isinstance(target,str) or not isinstance(source,str) or target in seen:
            raise ValueError('Invalid fixture addition')
        if target in base_files:raise ValueError('Fixture addition shadows pinned source')
        src=within(repo,source)
        if not source.startswith('work/') or src.suffix.lower() not in ('.json','.jsonl','.txt','.xodr'):
            raise ValueError('Fixture addition must be portable text under work')
        if sha(src)!=item.get('sha256'):
            raise ValueError('Fixture addition changed: '+source)
        seen.add(target);sources[target]=src
    return recipe,base,sources


def materialize(repo, recipe_path, output):
    recipe,base,sources=inspect(repo,recipe_path)
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh fixture directory')
    shutil.copytree(base,output)
    for relative in recipe['remove']:
        within(output,relative).unlink()
    for relative,source in sources.items():
        target=within(output,relative);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    return {'recipe_sha256':sha(recipe_path),'base_sha256':digest(tree(base)),
            'fixture_sha256':digest(tree(output)),'output':str(output)}
