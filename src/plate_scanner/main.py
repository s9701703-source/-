"""CLI entrypoint: python -m plate_scanner.main --config config.yaml"""
from __future__ import annotations

import argparse
import signal
import sys

from plate_scanner.app import PlateScannerApp, configure_logging
from plate_scanner.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dual-mirror license plate + GPS scanner")
    parser.add_argument("--config", default="config.yaml", help="path to config YAML file")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    configure_logging(config)

    app = PlateScannerApp(config)
    signal.signal(signal.SIGINT, lambda *_: app.request_stop())
    signal.signal(signal.SIGTERM, lambda *_: app.request_stop())

    app.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
