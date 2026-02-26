"""Quick database validation script for Phase 1.

Usage:
    python scripts/validate_db.py
"""
import os
import sys
from pathlib import Path

# Always run relative to project root so ./data/mitre.db resolves correctly
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import engine
from sqlalchemy import text

CHECKS = [
    ("Row counts", [
        ("tactics",              "SELECT COUNT(*) FROM tactics"),
        ("techniques (total)",   "SELECT COUNT(*) FROM techniques"),
        ("techniques (parent)",  "SELECT COUNT(*) FROM techniques WHERE is_subtechnique=0"),
        ("techniques (sub)",     "SELECT COUNT(*) FROM techniques WHERE is_subtechnique=1"),
        ("mitigations",          "SELECT COUNT(*) FROM mitigations"),
        ("technique_tactic",     "SELECT COUNT(*) FROM technique_tactic"),
        ("technique_mitigation", "SELECT COUNT(*) FROM technique_mitigation"),
        ("sync_logs",            "SELECT COUNT(*) FROM sync_logs"),
    ]),
    ("All 14 tactics", [
        ("tactics list", "SELECT attack_id || '  ' || name FROM tactics ORDER BY attack_id"),
    ]),
    ("Sample techniques", [
        ("T1078 exists",  "SELECT attack_id || '  ' || name FROM techniques WHERE attack_id='T1078'"),
        ("T1078.001",     "SELECT attack_id || '  ' || name FROM techniques WHERE attack_id='T1078.001'"),
    ]),
    ("Relationship spot-check (T1078 mitigations)", [
        ("T1078 mitigations", """
            SELECT m.attack_id, m.name
            FROM mitigations m
            JOIN technique_mitigation tm ON m.id = tm.mitigation_id
            JOIN techniques t ON t.id = tm.technique_id
            WHERE t.attack_id = 'T1078'
            ORDER BY m.attack_id
        """),
    ]),
    ("Relationship descriptions (sample)", [
        ("rel_desc sample", """
            SELECT t.attack_id, m.attack_id, substr(tm.relationship_description, 1, 80)
            FROM technique_mitigation tm
            JOIN techniques t ON t.id = tm.technique_id
            JOIN mitigations m ON m.id = tm.mitigation_id
            WHERE tm.relationship_description IS NOT NULL
            LIMIT 3
        """),
    ]),
]

PASS = "[PASS]"
FAIL = "[FAIL]"

def run():
    errors = 0
    with engine.connect() as conn:
        for section, queries in CHECKS:
            print(f"\n{'=' * 50}")
            print(f"  {section}")
            print('=' * 50)
            for label, sql in queries:
                rows = conn.execute(text(sql)).fetchall()
                for row in rows:
                    val = row[0] if len(row) == 1 else "  |  ".join(str(c) for c in row)
                    print(f"  {label}: {val}")

    # Simple assertions
    print(f"\n{'=' * 50}")
    print("  Assertions")
    print('=' * 50)
    with engine.connect() as conn:
        checks = [
            ("tactics == 14",            "SELECT COUNT(*) FROM tactics",                          14),
            ("techniques >= 600",         "SELECT COUNT(*) FROM techniques",                       600),
            ("subtechniques >= 400",      "SELECT COUNT(*) FROM techniques WHERE is_subtechnique=1", 400),
            ("mitigations >= 40",         "SELECT COUNT(*) FROM mitigations",                      40),
            ("technique_tactic >= 700",   "SELECT COUNT(*) FROM technique_tactic",                 700),
            ("technique_mitigation >= 400","SELECT COUNT(*) FROM technique_mitigation",            400),
            ("T1078 exists",              "SELECT COUNT(*) FROM techniques WHERE attack_id='T1078'", 1),
            ("rel_desc not all null",     "SELECT COUNT(*) FROM technique_mitigation WHERE relationship_description IS NOT NULL", 1),
        ]
        for label, sql, minimum in checks:
            actual = conn.execute(text(sql)).scalar()
            ok = actual >= minimum
            status = PASS if ok else FAIL
            print(f"  {status}  {label}: {actual} (min {minimum})")
            if not ok:
                errors += 1

    print()
    if errors == 0:
        print("  All checks passed. Phase 1 database is ready.")
    else:
        print(f"  {errors} check(s) failed.")
    return errors


if __name__ == "__main__":
    sys.exit(run())
