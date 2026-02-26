# -*- coding: utf-8 -*-
"""Manual sync script for Phase 1 verification.

Run this independently (without starting FastAPI) to download and
parse MITRE ATT&CK STIX data into the SQLite database.

Usage:
    python scripts/manual_sync.py

Expected output:
    [OK] enterprise-attack: 14 tactics, 600+ techniques, 43 mitigations

Then verify with:
    sqlite3 data/mitre.db "SELECT COUNT(*) FROM techniques;"
"""
import asyncio
import logging
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Always run relative to project root so ./data/mitre.db resolves correctly
import os
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    from app.config import settings
    from app.database import SessionLocal, init_db
    from app.sync.downloader import download_stix
    from app.sync.parser import sync_domain

    # Ensure directories exist
    settings.stix_data_dir.mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    # Initialize DB schema
    init_db()
    logger.info("Database schema ready")

    for domain in settings.mitre_domains:
        print(f"\n>> Syncing domain: {domain}")

        print("   Downloading STIX data...")
        stix_file = await download_stix(domain, settings.stix_data_dir)
        print(f"   STIX file: {stix_file} ({stix_file.stat().st_size / 1_048_576:.1f} MB)")

        print("   Parsing and upserting to database...")
        with SessionLocal() as db:
            stats = sync_domain(domain, stix_file, db)
            db.commit()

        print(
            f"\n   [OK] {domain}: "
            f"{stats['tactics']} tactics, "
            f"{stats['techniques']} techniques, "
            f"{stats['mitigations']} mitigations"
        )

    print("\n-- Verification queries --")
    from sqlalchemy import text
    from app.database import engine

    with engine.connect() as conn:
        for table in ["tactics", "techniques", "mitigations", "technique_tactic", "technique_mitigation", "sync_logs"]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"   {table}: {count} rows")


if __name__ == "__main__":
    asyncio.run(main())
