"""
Database module for storing scan history.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import sqlite3
import threading
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime
from config import CONFIG


@dataclass
class ScanRecord:
    """A single scan record."""
    id: Optional[int]
    timestamp: str
    decoded_data: str
    overall_grade: int
    overall_grade_char: str
    grade_contrast: int
    grade_modulation: int
    grade_anu: int
    grade_gnu: int
    grade_uec: int
    grade_fpd: int
    r_rms: float
    r_msc: float
    modulation: float
    axial_nonuniformity: float
    grid_nonuniformity: float
    unused_error_correction: float
    fixed_pattern_damage: float
    width: int
    height: int
    modules_count: int
    decode_success: int
    thumbnail: str  # Base64 encoded thumbnail

    def to_dict(self):
        d = asdict(self)
        return d


class Database:
    """SQLite database for scan history."""

    def __init__(self, db_path: str = CONFIG.DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                decoded_data TEXT,
                overall_grade INTEGER,
                overall_grade_char TEXT,
                grade_contrast INTEGER,
                grade_modulation INTEGER,
                grade_anu INTEGER,
                grade_gnu INTEGER,
                grade_uec INTEGER,
                grade_fpd INTEGER,
                r_rms REAL,
                r_msc REAL,
                modulation REAL,
                axial_nonuniformity REAL,
                grid_nonuniformity REAL,
                unused_error_correction REAL,
                fixed_pattern_damage REAL,
                width INTEGER,
                height INTEGER,
                modules_count INTEGER,
                decode_success INTEGER,
                thumbnail TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON scans(timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grade ON scans(overall_grade DESC)
        """)
        conn.commit()
        conn.close()

    def add_scan(self, record: ScanRecord) -> int:
        """Add a scan record. Returns the record ID."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scans (
                timestamp, decoded_data, overall_grade, overall_grade_char,
                grade_contrast, grade_modulation, grade_anu, grade_gnu,
                grade_uec, grade_fpd, r_rms, r_msc, modulation,
                axial_nonuniformity, grid_nonuniformity, unused_error_correction,
                fixed_pattern_damage, width, height, modules_count,
                decode_success, thumbnail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.timestamp, record.decoded_data, record.overall_grade,
            record.overall_grade_char, record.grade_contrast, record.grade_modulation,
            record.grade_anu, record.grade_gnu, record.grade_uec, record.grade_fpd,
            record.r_rms, record.r_msc, record.modulation, record.axial_nonuniformity,
            record.grid_nonuniformity, record.unused_error_correction,
            record.fixed_pattern_damage, record.width, record.height,
            record.modules_count, record.decode_success, record.thumbnail,
        ))
        scan_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Prune old records
        self._prune()
        return scan_id

    def get_history(self, limit: int = CONFIG.HISTORY_LIMIT,
                     grade_filter: Optional[int] = None) -> List[ScanRecord]:
        """Get scan history."""
        conn = self._get_connection()
        cur = conn.cursor()

        query = "SELECT * FROM scans"
        params = []
        if grade_filter is not None:
            query += " WHERE overall_grade = ?"
            params.append(grade_filter)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        records = []
        for row in rows:
            records.append(ScanRecord(*row))
        return records

    def get_statistics(self) -> dict:
        """Get scan statistics."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scans")
        total = cur.fetchone()[0]

        if total == 0:
            conn.close()
            return {
                "total": 0, "grades": {}, "avg_grade": 0.0,
                "pass_rate": 0.0, "avg_rms": 0.0
            }

        # Grade distribution
        cur.execute("""
            SELECT overall_grade, COUNT(*) FROM scans
            GROUP BY overall_grade ORDER BY overall_grade
        """)
        grade_counts = dict(cur.fetchall())

        # Average values
        cur.execute("""
            SELECT AVG(overall_grade), AVG(r_rms), AVG(modulation)
            FROM scans
        """)
        avg_row = cur.fetchone()

        # Pass rate (grade >= 2)
        cur.execute("SELECT COUNT(*) FROM scans WHERE overall_grade >= 2")
        passed = cur.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "grades": grade_counts,
            "avg_grade": float(avg_row[0] or 0),
            "avg_rms": float(avg_row[1] or 0),
            "avg_modulation": float(avg_row[2] or 0),
            "pass_rate": passed / total * 100 if total > 0 else 0,
        }

    def clear_history(self):
        """Clear all scan history."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM scans")
        conn.commit()
        conn.close()

    def _prune(self):
        """Remove old records beyond HISTORY_LIMIT."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM scans WHERE id NOT IN (
                SELECT id FROM scans ORDER BY id DESC LIMIT ?
            )
        """, (CONFIG.HISTORY_LIMIT,))
        conn.commit()
        conn.close()
