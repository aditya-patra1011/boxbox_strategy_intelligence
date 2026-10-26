import argparse
from datetime import date

from .jolpica import Client
from .season import ingest_season
from .store import DEFAULT_PATH, connect


def main():
    ap = argparse.ArgumentParser(prog="python -m ingest", description="Update the BoxBox Race Centre store.")
    ap.add_argument("--season", type=int, default=date.today().year)
    ap.add_argument("--full", action="store_true", help="re-fetch standings for every round, not just new ones")
    ap.add_argument("--db", default=DEFAULT_PATH, help=f"SQLite file (default: {DEFAULT_PATH})")
    args = ap.parse_args()

    client = Client()
    conn = connect(args.db)
    try:
        ingest_season(client, conn, args.season, full=args.full)
    finally:
        conn.close()
    print(f"done: {client.requests} requests -> {args.db}")


if __name__ == "__main__":
    main()
