if __package__:
    from .app import main
else:
    # Allow PyCharm's "Current File" action to launch this entry point too.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nitrosense.app import main

main()
