"""
Scanner engine - main processing loop with continuous scanning.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import cv2
import time
import base64
import numpy as np
from io import BytesIO
from typing import Optional, Callable, List
from dataclasses import dataclass

from camera import CameraCapture
from detector import DataMatrixDetector
from quality import QualityAssessor, QualityResult
from database import Database, ScanRecord
from config import CONFIG


@dataclass
class ScanEvent:
    """A scan event with results."""
    frame: np.ndarray
    result: QualityResult
    detection_time_ms: float
    record: ScanRecord


class ScannerEngine:
    """
    Main scanner engine.
    Continuously captures frames, detects DataMatrix, assesses quality,
    and stores results in the database.
    """

    def __init__(self):
        self.camera = CameraCapture()
        self.detector = DataMatrixDetector()
        self.assessor = QualityAssessor()
        self.db = Database()
        self._running = False
        self._last_scan_id = None
        self._scan_count = 0
        self._last_log = ""
        self._log_lines: List[str] = []
        self._callback: Optional[Callable] = None
        self._frame_callback: Optional[Callable] = None
        self._last_decoded = ""
        self._last_decoded_time = 0.0
        self._dedup_window = 2.0  # seconds

    def set_callback(self, callback: Callable[[ScanEvent], None]):
        """Set callback for scan events."""
        self._callback = callback

    def set_frame_callback(self, callback: Callable[[np.ndarray, Optional[QualityResult]], None]):
        """Set callback for frame updates."""
        self._frame_callback = callback

    def start(self) -> bool:
        """Start the scanner engine."""
        if not self.camera.open():
            self._log("ОШИБКА: Не удалось открыть камеру")
            return False

        self.camera.start()
        self._running = True
        self._log("Сканер запущен. Поиск DataMatrix...")
        return True

    def stop(self):
        """Stop the scanner engine."""
        self._running = False
        self.camera.stop()
        self._log("Сканер остановлен")

    def process_frame(self, frame: np.ndarray) -> Optional[QualityResult]:
        """
        Process a single frame - detect and assess DataMatrix.
        Returns QualityResult if DataMatrix found and decoded.
        """
        t0 = time.time()

        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        # Find square candidates
        squares = self.detector.find_squares(gray, frame)

        best_result: Optional[QualityResult] = None
        best_score = -1

        for sq in squares:
            # Check if it's a DataMatrix
            if not self.detector.is_data_matrix(sq.roi):
                continue

            # Try to decode
            decoded_data = ""
            modules = None
            try:
                from pylibdmtx import decode
                results = decode(sq.roi, timeout=100, max_count=1)
                if results:
                    decoded_data = results[0].data.decode('utf-8', errors='replace')
                    modules = self.detector.extract_modules(sq.roi, len(decoded_data))
            except ImportError:
                decoded_data = "DM-DETECTED"
            except Exception:
                decoded_data = ""

            # Assess quality
            result = self.assessor.assess(sq.roi, decoded_data, modules)
            result.width = sq.roi.shape[1]
            result.height = sq.roi.shape[0]
            result.decode_success = bool(decoded_data)

            # Score = overall grade (higher is better)
            score = result.overall_grade * 100 + result.r_rms * 50
            if score > best_score:
                best_score = score
                best_result = result

        if best_result is not None:
            dt = (time.time() - t0) * 1000
            self._log(f"DataMatrix найден: {best_result.decoded_data[:30]} | "
                       f"Оценка: {best_result.overall_grade_char} | {dt:.0f}ms")

            # Save to database
            record = self._make_record(best_result, frame, sq)
            scan_id = self.db.add_scan(record)
            best_result.decoded_data = record.decoded_data
            self._last_scan_id = scan_id
            self._scan_count += 1

            # Trigger callbacks
            event = ScanEvent(
                frame=frame,
                result=best_result,
                detection_time_ms=dt,
                record=record,
            )
            if self._callback:
                self._callback(event)

        return best_result

    def _make_record(self, result: QualityResult, frame: np.ndarray,
                      sq) -> ScanRecord:
        """Create a database record from a quality result."""
        # Create thumbnail
        thumbnail = ""
        try:
            # Crop and resize for thumbnail
            x1 = max(0, int(sq.centroid[0] - sq.side_len / 2))
            y1 = max(0, int(sq.centroid[1] - sq.side_len / 2))
            x2 = min(frame.shape[1], int(sq.centroid[0] + sq.side_len / 2))
            y2 = min(frame.shape[0], int(sq.centroid[1] + sq.side_len / 2))
            roi = frame[y1:y2, x1:x2]
            resized = cv2.resize(roi, (64, 64), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 60])
            thumbnail = base64.b64encode(buf).decode('utf-8')
        except Exception:
            pass

        return ScanRecord(
            id=None,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            decoded_data=result.decoded_data[:200] if result.decoded_data else "",
            overall_grade=result.overall_grade,
            overall_grade_char=result.overall_grade_char,
            grade_contrast=result.grade_contrast,
            grade_modulation=result.grade_modulation,
            grade_anu=result.grade_anu,
            grade_gnu=result.grade_gnu,
            grade_uec=result.grade_uec,
            grade_fpd=result.grade_fpd,
            r_rms=result.r_rms,
            r_msc=result.r_msc,
            modulation=result.modulation,
            axial_nonuniformity=result.axial_nonuniformity,
            grid_nonuniformity=result.grid_nonuniformity,
            unused_error_correction=result.unused_error_correction,
            fixed_pattern_damage=result.fixed_pattern_damage,
            width=result.width,
            height=result.height,
            modules_count=result.modules_count,
            decode_success=1 if result.decode_success else 0,
            thumbnail=thumbnail,
        )

    def run_loop(self):
        """Main continuous scanning loop."""
        frame_interval = CONFIG.SCAN_INTERVAL_MS / 1000.0
        last_process = 0.0

        while self._running:
            now = time.time()

            if now - last_process < frame_interval:
                time.sleep(0.01)
                continue

            frame = self.camera.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # Process frame
            result = self.process_frame(frame)

            # Update frame display callback
            if self._frame_callback:
                self._frame_callback(frame, result)

            last_process = now

    def get_camera_properties(self) -> dict:
        return self.camera.get_properties()

    def _log(self, message: str):
        """Add a log message."""
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        self._log_lines.append(line)
        if len(self._log_lines) > CONFIG.LOG_MAX_LINES:
            self._log_lines = self._log_lines[-CONFIG.LOG_MAX_LINES:]
        self._last_log = line

    def get_logs(self) -> List[str]:
        return self._log_lines.copy()

    def get_history(self, limit: int = 100) -> List[ScanRecord]:
        return self.db.get_history(limit=limit)

    def get_statistics(self) -> dict:
        return self.db.get_statistics()

    def clear_history(self):
        self.db.clear_history()
        self._log("История очищена")
