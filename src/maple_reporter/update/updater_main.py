"""PyInstaller entry point for the small portable-bundle updater."""

from maple_reporter.update.updater import main


if __name__ == "__main__":
    raise SystemExit(main())
