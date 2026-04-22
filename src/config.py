"""
Application configuration - all adjustable parameters in one place.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


class Config:
    """Application configuration with defaults matching GOST R 57302-2016 requirements."""

    # Camera settings
    CAMERA_INDEX: int = 0
    CAMERA_WIDTH: int = 1920
    CAMERA_HEIGHT: int = 1080
    CAMERA_FPS: int = 30

    # Scanning settings
    SCAN_INTERVAL_MS: int = 100  # Camera poll interval (ms)
    SQUARE_MIN_SIZE: int = 20     # Minimum square side to consider (px)
    SQUARE_MAX_SIZE: int = 2000   # Maximum square side (px)
    ASPECT_TOLERANCE: float = 0.2  # Tolerance for square detection aspect ratio
    PERIMETER_TOLERANCE: float = 0.1  # Tolerance for perimeter matching
    SQUARE_MARGIN: float = 0.3   # Area margin around square for cropping

    # DataMatrix validation
    DM_MIN_SIZE: int = 10  # Minimum DataMatrix side (modules)
    DM_MAX_SIZE: int = 144  # Maximum DataMatrix side (modules)

    # Quality thresholds (GOST R 57302-2016 / ISO/IEC 15415 based)
    # Grade mapping: 4=A, 3=B, 2=C, 1=D, 0=F
    # Overall = min of all parameters
    REFERENCE_GRADE_THRESHOLDS = {
        4: {"RMSC": 0.70, "MOD": 0.50, "ANU": 0.050, "GNU": 0.070, "UEC": 0.50, "FPD": 0.05},
        3: {"RMSC": 0.60, "MOD": 0.45, "ANU": 0.080, "GNU": 0.100, "UEC": 0.50, "FPD": 0.07},
        2: {"RMSC": 0.50, "MOD": 0.40, "ANU": 0.100, "GNU": 0.150, "UEC": 0.50, "FPD": 0.10},
        1: {"RMSC": 0.40, "MOD": 0.35, "ANU": 0.150, "GNU": 0.200, "UEC": 0.50, "FPD": 0.15},
    }

    # Display settings
    HISTORY_LIMIT: int = 500  # Maximum records in history table
    LOG_MAX_LINES: int = 200  # Maximum log messages in UI

    # Database
    DB_PATH: str = "datamatrix_scanner.db"

    # Window settings
    WINDOW_TITLE: str = "Сканер качества печати DataMatrix | ГОСТ Р 57302-2016"
    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 800

    def __init__(self):
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(self, key.upper()):
                        setattr(self, key.upper(), value)
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                data = {k: getattr(self, k) for k in dir(self)
                        if k.isupper() and not k.startswith("_")}
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass


CONFIG = Config()
