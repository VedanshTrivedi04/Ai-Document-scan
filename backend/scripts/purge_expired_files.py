"""
Run the document retention job by hand (app/services/retention_service.py).

    python -m scripts.purge_expired_files            # dry run: only counts
    python -m scripts.purge_expired_files --apply    # removes the files

Removal cannot be undone, so the default only reports how many files are past
DOCUMENT_RETENTION_DAYS.
"""
from __future__ import annotations

import argparse
import json

from app.services import retention_service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="remove the files (default: dry run)")
    args = parser.parse_args()
    print(json.dumps(retention_service.purge_expired_files(dry_run=not args.apply), indent=2, default=str))


if __name__ == "__main__":
    main()
