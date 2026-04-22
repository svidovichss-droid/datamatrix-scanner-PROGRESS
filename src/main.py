"""
DataMatrix Print Quality Scanner
ГОСТ Р 57302-2016

Author: А. Свидович / А. Петляков для PROGRESS
"""
import sys
import os
import warnings
import traceback

# Suppress warnings
warnings.filterwarnings("ignore")

# Set DPI awareness for Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        pass


def main():
    """Application entry point."""
    try:
        from PyQt5 import QtWidgets, QtCore
        from ui import MainWindow
    except ImportError as e:
        print(f"Ошибка импорта PyQt5: {e}")
        print("Установите зависимости: pip install -r requirements.txt")
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

    # Enable OpenCV multithreading
    os.environ["OPENCV_NUM_THREADS"] = "1"

    app = QtWidgets.QApplication(sys.argv)

    # Application styling
    app.setStyle("Fusion")

    # Set application font
    font = QtGui.QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(9)
    app.setFont(font)

    # Set stylesheet
    app.setStyleSheet("""
        QToolTip {
            background-color: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 4px;
        }
        QMessageBox {
            background-color: #161b22;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #30363d;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #58a6ff;
        }
    """)

    from PyQt5 import QtGui

    # Create and show window
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
