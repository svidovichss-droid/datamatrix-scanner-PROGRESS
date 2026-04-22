"""
Main UI for DataMatrix Scanner.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import sys
import cv2
import base64
import time
import traceback
import numpy as np
from io import BytesIO
from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QTableWidget, QTableWidgetItem, QPushButton,
                              QGroupBox, QFrame, QScrollArea, QStatusBar,
                              QHeaderView, QSplitter, QMessageBox, QComboBox,
                              QProgressBar, QStyledItemDelegate, QStyle,
                              QPlainTextEdit)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QIcon
from PyQt5.QtChart import QChartView, QChart, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis

from scanner import ScannerEngine, ScanEvent
from database import ScanRecord
from config import CONFIG


# ──────────────────────────────────────────────────────────────
# Grade colors and icons
# ──────────────────────────────────────────────────────────────
GRADE_COLORS = {
    4: "#1B5E20",   # A - Dark green
    3: "#F57F17",   # B - Orange
    2: "#E65100",   # C - Deep orange
    1: "#B71C1C",   # D - Red
    0: "#212121",   # F - Black
}

GRADE_LABELS = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}

PALETTE_QT = {
    4: QtGui.QColor("#1B5E20"),
    3: QtGui.QColor("#F57F17"),
    2: QtGui.QColor("#E65100"),
    1: QtGui.QColor("#B71C1C"),
    0: QtGui.QColor("#212121"),
}


class GradeDelegate(QStyledItemDelegate):
    """Delegate that colors cells based on grade values."""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        grade = index.data(Qt.UserRole)
        if grade is not None:
            try:
                g = int(grade)
                color = PALETTE_QT.get(g, Qt.gray)
                option.palette.setColor(QPalette.Text, Qt.white)
                option.palette.setColor(QPalette.Highlight, color)
            except (ValueError, TypeError):
                pass


# ──────────────────────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────────────────────
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(CONFIG.WINDOW_TITLE)
        self.setMinimumSize(CONFIG.WINDOW_WIDTH, CONFIG.WINDOW_HEIGHT)

        # Scanner engine
        self.engine = ScannerEngine()
        self.engine.set_callback(self._on_scan_event)
        self.engine.set_frame_callback(self._on_frame_update)

        # Worker thread
        self.worker_thread = None

        # Last frame for display
        self._current_frame = None
        self._current_result = None
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(33)  # ~30 fps display

        # Stats update timer
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(1000)

        self._setup_ui()
        self._setup_worker()
        self._update_camera_label()
        self._update_stats()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left panel: camera + controls
        left_panel = self._create_left_panel()

        # Right panel: results + history
        right_panel = self._create_right_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к сканированию")

    def _create_left_panel(self) -> QWidget:
        """Create left panel with camera view and controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Camera group
        cam_group = QGroupBox("Камера")
        cam_layout = QVBoxLayout(cam_group)

        # Camera label (QLabel for video)
        self.cam_label = QLabel()
        self.cam_label.setMinimumSize(640, 480)
        self.cam_label.setStyleSheet(
            "background-color: #1a1a2e; border: 2px solid #333; "
            "border-radius: 4px; color: #555; font-size: 18px; "
            "qproperty-alignment: AlignCenter;"
        )
        self.cam_label.setText("  Нет видеопотока\n  (нажмите Старт)")
        self.cam_label.setAlignment(Qt.AlignCenter)
        cam_layout.addWidget(self.cam_label)

        # Controls row
        controls_row = QHBoxLayout()

        self.btn_start = QPushButton("  СТАРТ  ")
        self.btn_start.setStyleSheet(self._btn_style("#27ae60"))
        self.btn_start.clicked.connect(self._on_start)

        self.btn_stop = QPushButton("  СТОП  ")
        self.btn_stop.setStyleSheet(self._btn_style("#e74c3c"))
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)

        self.btn_clear = QPushButton("  Очистить историю  ")
        self.btn_clear.setStyleSheet(self._btn_style("#7f8c8d"))
        self.btn_clear.clicked.connect(self._on_clear_history)

        controls_row.addWidget(self.btn_start)
        controls_row.addWidget(self.btn_stop)
        controls_row.addWidget(self.btn_clear)
        controls_row.addStretch()

        cam_layout.addLayout(controls_row)

        # Camera info
        self.cam_info_label = QLabel("Камера: не подключена")
        self.cam_info_label.setStyleSheet("color: #888; font-size: 11px;")
        cam_layout.addWidget(self.cam_info_label)

        layout.addWidget(cam_group, 1)

        # Current result group
        result_group = QGroupBox("Последний результат")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QLabel("Ожидание сканирования...")
        self.result_text.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 12px; "
            "background-color: #0d1117; color: #e6edf3; "
            "border: 1px solid #30363d; border-radius: 4px; "
            "padding: 8px;"
        )
        self.result_text.setWordWrap(True)
        self.result_text.setMinimumHeight(160)
        self.result_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

        # Grade badge
        self.grade_badge = QLabel()
        self.grade_badge.setAlignment(Qt.AlignCenter)
        self.grade_badge.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: white; "
            "background-color: #333; border-radius: 8px; padding: 10px;"
        )
        self.grade_badge.setText("?")
        result_layout.addWidget(self.grade_badge)

        # Log area
        log_group = QGroupBox("Журнал событий")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QPlainTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 10px; "
            "background-color: #0d1117; color: #7ee787; "
            "border: none;"
        )
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with statistics and history."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Statistics group
        stats_group = QGroupBox("Статистика")
        stats_layout = QGridLayout(stats_group)

        self.stat_total = self._make_stat_label("0")
        self.stat_pass = self._make_stat_label("0%")
        self.stat_avg = self._make_stat_label("-")
        self.stat_grade_dist = self._make_stat_label("-")

        stats_layout.addWidget(QLabel("Всего сканирований:"), 0, 0)
        stats_layout.addWidget(self.stat_total, 0, 1)
        stats_layout.addWidget(QLabel("Процент годных (≥C):"), 1, 0)
        stats_layout.addWidget(self.stat_pass, 1, 1)
        stats_layout.addWidget(QLabel("Средняя оценка:"), 2, 0)
        stats_layout.addWidget(self.stat_avg, 2, 1)

        layout.addWidget(stats_group)

        # History group
        hist_group = QGroupBox("История сканирований")
        hist_layout = QVBoxLayout(hist_group)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Фильтр по оценке:"))
        self.grade_filter = QComboBox()
        self.grade_filter.addItems(["Все", "A (4)", "B (3)", "C (2)", "D (1)", "F (0)"])
        self.grade_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.grade_filter)
        filter_row.addStretch()
        hist_layout.addLayout(filter_row)

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Время", "Данные", "Оценка", "RMSC", "MOD", "ANU", "GNU"
        ])
        self.history_table.setMaximumHeight(300)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                gridline-color: #30363d;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #e6edf3;
                padding: 6px;
                border: 1px solid #30363d;
                font-weight: bold;
            }
        """)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hist_layout.addWidget(self.history_table)

        # Row click to show details
        self.history_table.cellClicked.connect(self._on_history_row_clicked)

        layout.addWidget(hist_group, 1)

        return panel

    def _make_stat_label(self, value: str) -> QLabel:
        label = QLabel(value)
        label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #58a6ff; "
            "background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 4px 12px;"
        )
        label.setAlignment(Qt.AlignCenter)
        return label

    def _btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {color}cc;
            }}
            QPushButton:disabled {{
                background-color: #444;
                color: #888;
            }}
        """

    def _setup_worker(self):
        """Setup the worker thread for scanning."""
        self.worker = ScanWorker(self.engine)
        self.worker.log_updated.connect(self._append_log)

    def _on_start(self):
        if not self.engine.start():
            QMessageBox.critical(
                self, "Ошибка",
                "Не удалось открыть камеру.\n"
                "Проверьте подключение камеры и драйверы."
            )
            return

        self.worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_bar.showMessage("Сканирование активно...")
        self._update_camera_label()

    def _on_stop(self):
        self.engine.stop()
        self.worker.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_bar.showMessage("Сканирование остановлено")
        self._update_camera_label()

    def _on_clear_history(self):
        reply = QMessageBox.question(
            self, "Очистить историю",
            "Удалить все записи сканирований?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.engine.clear_history()
            self._refresh_history()
            self._update_stats()

    def _on_filter_changed(self, index: int):
        self._refresh_history()

    def _on_scan_event(self, event: ScanEvent):
        """Handle a scan event from the scanner."""
        # Update result display
        self._current_result = event.result
        self._update_result_display(event.result)
        self._refresh_history()
        self._update_stats()

        # Update status bar
        self.status_bar.showMessage(
            f"DataMatrix: {event.result.decoded_data[:40]} | "
            f"Оценка: {event.result.overall_grade_char}"
        )

    def _on_frame_update(self, frame: np.ndarray, result):
        """Called on each frame update."""
        self._current_frame = frame

    def _on_history_row_clicked(self, row: int):
        """Show details when a history row is clicked."""
        record_id = self.history_table.item(row, 0).data(Qt.UserRole)
        if record_id is None:
            return

        records = self.engine.get_history(limit=CONFIG.HISTORY_LIMIT)
        for rec in records:
            if rec.id == record_id:
                self._show_record_detail(rec)
                break

    def _show_record_detail(self, rec: ScanRecord):
        """Show a detailed view of a scan record."""
        grade_colors_map = {
            4: "#1B5E20", 3: "#F57F17", 2: "#E65100", 1: "#B71C1C", 0: "#212121"
        }
        color = grade_colors_map.get(rec.overall_grade, "#333")

        text = f"""
        <h2 style="color: {color};">Оценка: {rec.overall_grade_char} ({rec.overall_grade}/4)</h2>
        <hr>
        <b>Время:</b> {rec.timestamp}<br>
        <b>Данные:</b> {rec.decoded_data}<br>
        <b>Размер:</b> {rec.width}x{rec.height} px<br>
        <b>Модулей:</b> {rec.modules_count}x{rec.modules_count}<br>
        <hr>
        <b>Параметры:</b><br>
        <table style="font-family: monospace;">
        <tr><td>Контраст (RMSC):</td><td><b>{rec.r_rms:.4f}</b></td><td>→ {rec.grade_contrast}</td></tr>
        <tr><td>Модуляция (MOD):</td><td><b>{rec.modulation:.4f}</b></td><td>→ {rec.grade_modulation}</td></tr>
        <tr><td>Осевая неравномерность:</td><td><b>{rec.axial_nonuniformity:.4f}</b></td><td>→ {rec.grade_anu}</td></tr>
        <tr><td>Сеточная неравномерность:</td><td><b>{rec.grid_nonuniformity:.4f}</b></td><td>→ {rec.grade_gnu}</td></tr>
        <tr><td>Неисп. коррекция (UEC):</td><td><b>{rec.unused_error_correction:.4f}</b></td><td>→ {rec.grade_uec}</td></tr>
        <tr><td>Повреждение шаблона (FPD):</td><td><b>{rec.fixed_pattern_damage:.4f}</b></td><td>→ {rec.grade_fpd}</td></tr>
        </table>
        <hr>
        <b>Декодирование:</b> {"✓ Успешно" if rec.decode_success else "✗ Ошибка"}
        """

        QMessageBox.information(self, f"Детали сканирования #{rec.id}", text)

    def _update_display(self):
        """Update camera display - called on timer."""
        if self._current_frame is None:
            return

        try:
            frame = self._current_frame.copy()
            result = self._current_result

            # Draw overlay if result available
            if result is not None:
                h, w = frame.shape[:2]
                # Draw grade badge on frame
                grade = result.overall_grade_char
                color = PALETTE_QT.get(result.overall_grade, Qt.gray)
                cv2.rectangle(frame, (w - 80, 0), (w, 80), color.toRgb().name() if hasattr(color, 'toRgb') else "#333", -1)
                cv2.putText(frame, grade, (w - 65, 55),
                              cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

            # Convert to QPixmap
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            bytes_per_line = 3 * w
            qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)

            # Scale to fit label
            label_size = self.cam_label.size()
            scaled = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cam_label.setPixmap(scaled)

        except Exception:
            pass

    def _update_result_display(self, result):
        """Update the result text display."""
        if result is None:
            return

        grade_colors_map = {
            4: "#1B5E20", 3: "#F57F17", 2: "#E65100", 1: "#B71C1C", 0: "#212121"
        }
        color = grade_colors_map.get(result.overall_grade, "#333")

        # Grade badge
        self.grade_badge.setText(result.overall_grade_char)
        self.grade_badge.setStyleSheet(
            f"font-size: 48px; font-weight: bold; color: white; "
            f"background-color: {color}; border-radius: 8px; padding: 10px;"
        )

        # Text report
        self.result_text.setText(str(result))

    def _append_log(self, message: str):
        self.log_text.appendPlainText(message)
        # Auto-scroll
        scroll = self.log_text.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def _refresh_history(self):
        """Refresh the history table."""
        grade_filter_map = {0: None, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0}
        filter_val = grade_filter_map.get(self.grade_filter.currentIndex())

        records = self.engine.get_history(limit=CONFIG.HISTORY_LIMIT)
        if filter_val is not None:
            records = [r for r in records if r.overall_grade == filter_val]

        self.history_table.setRowCount(0)
        self.history_table.setRowCount(len(records))

        for i, rec in enumerate(records):
            self.history_table.setItem(i, 0, QTableWidgetItem(rec.timestamp))
            self.history_table.item(i, 0).setData(Qt.UserRole, rec.id)

            data_text = rec.decoded_data[:40] + ("..." if len(rec.decoded_data) > 40 else "")
            self.history_table.setItem(i, 1, QTableWidgetItem(data_text))

            grade_item = QTableWidgetItem(f"{rec.overall_grade_char} ({rec.overall_grade})")
            color = PALETTE_QT.get(rec.overall_grade, Qt.gray)
            grade_item.setBackground(QtGui.QBrush(color))
            grade_item.setForeground(QtGui.QBrush(Qt.white))
            grade_item.setData(Qt.UserRole, rec.overall_grade)
            self.history_table.setItem(i, 2, grade_item)

            self.history_table.setItem(i, 3, QTableWidgetItem(f"{rec.r_rms:.3f}"))
            self.history_table.setItem(i, 4, QTableWidgetItem(f"{rec.modulation:.3f}"))
            self.history_table.setItem(i, 5, QTableWidgetItem(f"{rec.axial_nonuniformity:.3f}"))
            self.history_table.setItem(i, 6, QTableWidgetItem(f"{rec.grid_nonuniformity:.3f}"))

    def _update_stats(self):
        """Update statistics display."""
        try:
            stats = self.engine.get_statistics()
            self.stat_total.setText(str(stats.get("total", 0)))
            self.stat_pass.setText(f"{stats.get('pass_rate', 0):.1f}%")
            avg_g = stats.get("avg_grade", 0)
            grade_labels = {0: "F", 1: "D", 2: "C", 3: "B", 4: "A"}
            avg_char = grade_labels.get(round(avg_g), "-")
            self.stat_avg.setText(f"{avg_char} ({avg_g:.1f})")
        except Exception:
            pass

    def _update_camera_label(self):
        props = self.engine.get_camera_properties()
        if props:
            self.cam_info_label.setText(
                f"Камера: {props.get('width', 0)}x{props.get('height', 0)} "
                f"@ {props.get('fps', 0):.0f} FPS | {props.get('backend', 'N/A')}"
            )
        else:
            self.cam_info_label.setText("Камера: не подключена")

    def closeEvent(self, event):
        self.engine.stop()
        self.worker.stop()
        event.accept()


# ──────────────────────────────────────────────────────────────
# Scanner Worker Thread
# ──────────────────────────────────────────────────────────────
class ScanWorker(QThread):
    log_updated = pyqtSignal(str)

    def __init__(self, engine: ScannerEngine):
        super().__init__()
        self.engine = engine
        self._running = True

    def run(self):
        try:
            self.engine.run_loop()
        except Exception as e:
            self.log_updated.emit(f"ОШИБКА потока: {e}")
            traceback.print_exc()

    def stop(self):
        self._running = False
