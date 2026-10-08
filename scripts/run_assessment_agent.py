"""CLI worker for the Background Autonomous AI Assessment Agent."""

from __future__ import annotations

import argparse
import time

from main import create_app
from services.deep_agent import assess_pending_talks


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan pending talk proposals with the Deep Agent.")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")
    parser.add_argument("--interval", type=int, default=45, help="Seconds between scans")
    parser.add_argument("--force", action="store_true", help="Re-evaluate proposals that already have a score")
    args = parser.parse_args()

    app = create_app({"ASSESSMENT_AGENT_AUTOSTART": False})
    while True:
        with app.app_context():
            results = assess_pending_talks(force=args.force)
        print(f"Assessed {len(results)} pending proposal(s).")
        if args.once:
            break
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    main()
