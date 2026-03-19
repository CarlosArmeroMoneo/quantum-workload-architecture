from __future__ import annotations

import argparse

from aqs.db import apply_schema
from aqs.paths import default_schema_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the DuckDB warehouse")
    parser.add_argument("--db", required=True, help="Path to the DuckDB file")
    parser.add_argument("--schema", default=str(default_schema_path()), help="Path to the schema SQL file")
    parser.add_argument("--schema-version", default="aqs_schema_v0")
    args = parser.parse_args()
    db_path = apply_schema(args.db, args.schema, args.schema_version)
    print(f"Initialized warehouse at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
