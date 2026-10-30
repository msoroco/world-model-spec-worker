"""Run from project root: python3.11 -m scenario_pipeline.worker_exchange --help."""
import argparse
import json
import sys
from pathlib import Path
# Local pipeline imports intentionally remain outside the portable worker subset.
PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))
from .common import read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PIPELINE.parent)
    parser.add_argument('--root', type=Path, default=PIPELINE.parent / 'runs/scenario_pipeline')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('partition')
    p.add_argument('--set', required=True)
    p.add_argument('--count', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--assignments', type=Path, help='JSON list of assignment IDs; default entire explicitly requested set')
    p = sub.add_parser('export')
    p.add_argument('--partitions', nargs='+', type=Path, required=True)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--batch', required=True)
    p.add_argument('--max-workers', type=int, default=4)
    for command in ('init-worker', 'refresh-scaffold'):
        p = sub.add_parser(command)
        p.add_argument('--destination', type=Path, required=True)
    for cmd in ('check-return', 'import', 'freeze', 'adopt'):
        p = sub.add_parser(cmd)
        p.add_argument('--repo', type=Path, required=True)
        p.add_argument('--batch', required=True)
        if cmd in ('freeze', 'adopt'):
            p.add_argument('--db', type=Path, required=True)
            p.add_argument('--run', required=True)
        if cmd == 'freeze':
            p.add_argument('--base-revision', required=True)
            p.add_argument('--config', type=Path, required=True, help='Complete locally reviewed config; no inherited law/context')
        if cmd == 'adopt':
            p.add_argument('--plan', type=Path, required=True)
    p = sub.add_parser('adopt-case')
    for flag in ('repo','db'):
        p.add_argument('--'+flag,type=Path,required=True)
    for flag in ('batch','run','assignment','case','expected-cache-key'):
        p.add_argument('--'+flag,required=True)
    p.add_argument('--job',type=int,required=True)
    p = sub.add_parser('prepare-jobs')
    for flag in ('repo','db'):
        p.add_argument('--'+flag,type=Path,required=True)
    for flag in ('batch','run','assignment'):
        p.add_argument('--'+flag,required=True)
    p.add_argument('--cases-job',type=int,required=True)
    p.add_argument('--case',action='append',required=True)
    p = sub.add_parser('benchmark-decode')
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--frames', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--threads', nargs='+', type=int, default=[0, 4, 8])
    p = sub.add_parser('benchmark-render')
    p.add_argument('--videos', nargs=4, type=Path, required=True)
    p.add_argument('--frames', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--filter-threads', nargs='+', type=int, default=[1, 4])
    p.add_argument('--encoder-threads', nargs='+', type=int, default=[4, 8])
    p.add_argument('--overview-size', nargs=2, type=int, help='Optional saved downscale diagnostic width height')
    args = parser.parse_args()
    from . import exchange
    if args.command == 'partition':
        value = exchange.partition(args.root, args.set, args.count, args.output,
                                   read(args.assignments) if args.assignments else None)
    elif args.command == 'export':
        value = exchange.export(args.project, args.root, args.partitions, args.spec,
                                args.destination, args.batch, args.max_workers)
        value = {'batch_id': value['batch']['batch_id'], 'assignments': list(value['batch']['assignments']),
                 'destination': str(args.destination), 'dispatched': False}
    elif args.command == 'init-worker':
        value = exchange.init_worker(args.project, args.destination)
    elif args.command == 'refresh-scaffold':
        value = exchange.refresh_scaffold(args.project, args.destination)
    elif args.command == 'check-return':
        result = exchange.check_return(args.root, args.repo, args.batch)
        value = {k: v for k, v in result.items() if k != 'files'}
    elif args.command == 'import':
        value = exchange.import_return(args.root, args.repo, args.batch)
    elif args.command == 'prepare-jobs':
        from .local import prepare_manifest_jobs
        value=prepare_manifest_jobs(args.root,args.repo,args.batch,args.db,args.run,args.assignment,args.cases_job,args.case)
    elif args.command == 'adopt-case':
        from .local import adopt_manifest_case
        value=adopt_manifest_case(args.root,args.repo,args.batch,args.db,args.run,args.assignment,args.case,args.job,args.expected_cache_key)
    elif args.command in ('freeze', 'adopt'):
        from . import local
        if args.command == 'freeze':
            value = local.freeze(args.root, args.repo, args.batch, args.db, args.run, args.base_revision, args.config)
        else:
            value = local.adopt(args.root, args.repo, args.batch, args.db, args.run, args.plan)
    elif args.command == 'benchmark-render':
        from .media import benchmark_render
        value = benchmark_render(args.videos, args.frames, args.output, args.filter_threads, args.encoder_threads, args.overview_size)
    else:
        from .media import benchmark
        value = benchmark(args.video, args.frames, args.output, args.threads)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
