"""
DataMatrix detector - finds squares and validates them as DataMatrix.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

from config import CONFIG


@dataclass
class SquareCandidate:
    """Represents a detected square candidate."""
    polygon: np.ndarray  # 4x2 points
    area: float
    centroid: Tuple[float, float]
    side_len: float
    roi: np.ndarray  # Cropped ROI image
    aspect_ratio: float


class DataMatrixDetector:
    """Detects and validates DataMatrix codes in camera frames."""

    def __init__(self):
        self._approx_eps = 0.05

    def find_squares(self, gray: np.ndarray, frame: np.ndarray) -> List[SquareCandidate]:
        """Find all square-like contours in the image."""
        candidates = []

        # Apply edge detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Close gaps in edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        h, w = gray.shape

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < CONFIG.SQUARE_MIN_SIZE ** 2:
                continue
            if area > CONFIG.SQUARE_MAX_SIZE ** 2:
                continue

            # Approximate contour
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, self._approx_eps * peri, True)

            if len(approx) != 4:
                continue

            # Check convexity
            if not cv2.isContourConvex(approx):
                continue

            # Check area ratio (should be close to a square)
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), _ = rect
            expected_area = rw * rh
            if expected_area <= 0:
                continue

            area_ratio = area / expected_area
            if area_ratio < (1 - CONFIG.ASPECT_TOLERANCE):
                continue

            # Aspect ratio check
            aspect = max(rw, rh) / (min(rw, rh) + 1e-9)
            if aspect > (1 + CONFIG.ASPECT_TOLERANCE):
                continue

            # Check perimeter ratio
            expected_perimeter = 4 * ((rw + rh) / 2)
            peri_ratio = abs(peri - expected_perimeter) / expected_perimeter
            if peri_ratio > CONFIG.PERIMETER_TOLERANCE:
                continue

            # Convert to numpy array
            box = cv2.boxPoints(rect)
            box = np.int0(box)

            # Compute side length
            side = np.sqrt(area)

            # Extract ROI with margin
            x, y = int(cx - side / 2), int(cy - side / 2)
            margin = int(side * CONFIG.SQUARE_MARGIN)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(w, int(x + side) + margin)
            y2 = min(h, int(y + side) + margin)

            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            candidates.append(SquareCandidate(
                polygon=box.astype(np.float32),
                area=area,
                centroid=(float(cx), float(cy)),
                side_len=side,
                roi=roi.copy(),
                aspect_ratio=aspect,
            ))

        return candidates

    def is_data_matrix(self, roi: np.ndarray) -> bool:
        """
        Validate if the ROI contains a DataMatrix.
        Uses pylibdmtx if available, falls back to structural analysis.
        """
        try:
            from pylibdmtx import decode
            results = decode(roi, timeout=100, max_count=1)
            return len(results) > 0
        except ImportError:
            return self._structural_check(roi)

    def _structural_check(self, roi: np.ndarray) -> bool:
        """
        Fallback: structural analysis for DataMatrix detection.
        Checks for the characteristic L-shaped finder pattern and internal grid.
        """
        try:
            # Resize for consistent analysis
            size = 100
            resized = cv2.resize(roi, (size, size), interpolation=cv2.INTER_AREA)

            if len(resized.shape) == 3:
                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            else:
                gray = resized

            # Binarize
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Count border pixels (DataMatrix should have a border)
            h, w = binary.shape
            border_top = np.sum(binary[0, :] == 0)
            border_bottom = np.sum(binary[h - 1, :] == 0)
            border_left = np.sum(binary[:, 0] == 0)
            border_right = np.sum(binary[:, w - 1] == 0)

            total_border = border_top + border_bottom + border_left + border_right
            total_edge = 4 * size

            # Border should be mostly dark
            border_ratio = total_border / total_edge
            if border_ratio < 0.3:
                return False

            # Check internal structure - should have grid-like pattern
            inner = binary[5:-5, 5:-5]
            nonzero_ratio = np.count_nonzero(inner) / inner.size

            # DataMatrix should have significant dark/light ratio
            if nonzero_ratio < 0.1 or nonzero_ratio > 0.9:
                return False

            # Check corner patterns (L-shape finder pattern in corners)
            corner_size = 10
            corners = [
                binary[:corner_size, :corner_size],
                binary[:corner_size, -corner_size:],
                binary[-corner_size:, :corner_size],
                binary[-corner_size:, -corner_size:],
            ]

            corner_scores = []
            for corner in corners:
                # In DataMatrix, corners should have a specific L pattern
                dark_pixels = np.sum(corner == 0)
                corner_scores.append(dark_pixels / corner.size)

            # At least 2 corners should have significant dark pixel ratio
            significant_corners = sum(1 for s in corner_scores if s > 0.3)
            if significant_corners < 2:
                return False

            return True

        except Exception:
            return False

    def extract_modules(self, roi: np.ndarray, size_hint: int = 14) -> Optional[np.ndarray]:
        """
        Extract DataMatrix module grid from ROI.
        Returns 2D binary array of modules.
        """
        try:
            from pylibdmtx import decode
            results = decode(roi, timeout=100, max_count=1)
            if not results:
                return None

            result = results[0]
            data_size = result.data.shape[0]

            # Get the bounding rect of the decoded region
            if hasattr(result, 'rect'):
                rect = result.rect
            else:
                return None

            # Crop to DataMatrix region
            x, y = rect.left, rect.top
            dm_w, dm_h = rect.width, rect.height

            if dm_w <= 0 or dm_h <= 0:
                return None

            # Crop and resize to module grid
            x1 = max(0, y)
            y1 = max(0, x)
            x2 = min(roi.shape[0], y + dm_h)
            y2 = min(roi.shape[1], x + dm_w)

            dm_region = roi[x1:x2, y1:y2]

            if dm_region.size == 0:
                return None

            # Resize to module grid
            grid_size = data_size + 2  # Modules + finder pattern border
            resized = cv2.resize(dm_region, (grid_size, grid_size),
                                  interpolation=cv2.INTER_AREA)

            if len(resized.shape) == 3:
                gray_dm = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            else:
                gray_dm = resized

            # Binarize
            _, binary = cv2.threshold(gray_dm, 0, 255,
                                       cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            modules = (binary < 128).astype(np.uint8)

            return modules

        except Exception:
            return None
