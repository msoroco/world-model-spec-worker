"""Compatibility entrypoint for explicit-file update publication."""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from worker_exchange.updates import main
else:
    from .updates import main

if __name__ == '__main__':
    main()
