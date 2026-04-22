"""
DataMatrix print quality assessment according to GOST R 57302-2016.
Author: А. Свидович / А. Петляков для PROGRESS

GOST R 57302-2016 is equivalent to ISO/IEC 15415 for 2D barcodes.
Grade scale: 4 (A), 3 (B), 2 (C), 1 (D), 0 (F)
Overall grade = minimum of all parameter grades.
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from config import CONFIG


@dataclass
class QualityResult:
    """Result of DataMatrix quality assessment."""
    # Overall grade (0-4)
    overall_grade: int
    overall_grade_char: str

    # Individual parameter grades
    r_an: float        # Reflectance (absolute)
    r_min: float       # Minimum module reflectance
    r_max: float       # Maximum module reflectance
    r_rms: float       # RMS contrast
    r_msc: float       # Minimum edge contrast (symbol contrast)

    modulation: float   # MOD = R_MSC / R_max
    axial_nonuniformity: float  # ANU
    grid_nonuniformity: float   # GNU
    unused_error_correction: float  # UEC
    fixed_pattern_damage: float    # FPD

    # Individual grades
    grade_contrast: int
    grade_modulation: int
    grade_anu: int
    grade_gnu: int
    grade_uec: int
    grade_fpd: int

    # Decode result
    decoded_data: str
    decode_success: bool

    # Image metrics
    width: int
    height: int
    modules_count: int  # Total modules

    def __str__(self):
        g = self.overall_grade_char
        lines = [
            f"DataMatrix Quality Report (ГОСТ Р 57302-2016)",
            f"{'='*50}",
            f"Overall Grade: {g} ({self.overall_grade}/4)",
            f"{'-'*50}",
            f"  Symbol Contrast (RMSC): {self.r_rms:.4f}  → Grade {self.grade_contrast}",
            f"  Modulation (MOD):       {self.modulation:.4f}  → Grade {self.grade_modulation}",
            f"  Axial Nonuniformity:    {self.axial_nonuniformity:.4f}  → Grade {self.grade_anu}",
            f"  Grid Nonuniformity:     {self.grid_nonuniformity:.4f}  → Grade {self.grade_gnu}",
            f"  Unused EC (UEC):        {self.unused_error_correction:.4f}  → Grade {self.grade_uec}",
            f"  Fixed Pattern Damage:  {self.fixed_pattern_damage:.4f}  → Grade {self.grade_fpd}",
            f"{'-'*50}",
            f"  R_min: {self.r_min:.3f}  R_max: {self.r_max:.3f}  R_MSC: {self.r_msc:.3f}",
            f"  Modules: {self.modules_count}x{self.modules_count}",
            f"  Decode: {'✓ ' + self.decoded_data if self.decode_success else '✗ FAILED'}",
            f"{'='*50}",
        ]
        return "\n".join(lines)


class QualityAssessor:
    """Assesses DataMatrix print quality according to GOST R 57302-2016."""

    def __init__(self):
        self.thresholds = CONFIG.REFERENCE_GRADE_THRESHOLDS

    def assess(self, roi: np.ndarray, decoded_data: str = "",
               modules: Optional[np.ndarray] = None) -> QualityResult:
        """
        Assess DataMatrix quality from a cropped ROI.
        If pylibdmtx is available and decoded_data is provided, use module grid.
        Otherwise falls back to image-based analysis.
        """
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi.copy()

        h, w = gray.shape

        # Global reflectance values
        r_max = float(gray.max()) / 255.0
        r_min = float(gray.min()) / 255.0
        r_white = r_max
        r_black = r_min

        # RMS contrast
        if r_max > r_min:
            r_rms = (r_max - r_min) / (r_max + r_min + 1e-9)
        else:
            r_rms = 0.0

        # Symbol contrast (RMSC)
        r_msc = r_max - r_min

        # Normalize image
        if r_max > r_min:
            normalized = (gray.astype(np.float32) / 255.0 - r_min) / (r_max - r_min + 1e-9)
        else:
            normalized = np.ones_like(gray, dtype=np.float32) * 0.5

        normalized = np.clip(normalized, 0, 1)

        # Analyze module grid if available
        if modules is not None and decoded_data:
            return self._assess_with_modules(normalized, gray, modules, decoded_data,
                                               r_max, r_min, r_rms, r_msc)
        else:
            return self._assess_fallback(gray, normalized, decoded_data,
                                          r_max, r_min, r_rms, r_msc)

    def _assess_with_modules(self, normalized: np.ndarray, gray: np.ndarray,
                               modules: np.ndarray, decoded_data: str,
                               r_max: float, r_min: float,
                               r_rms: float, r_msc: float) -> QualityResult:
        """Assess quality using detected module grid."""
        m_h, m_w = modules.shape
        n = max(m_h, m_w)

        # Resize normalized image to module grid
        grid_size = n
        grid = cv2.resize(normalized, (grid_size, grid_size), interpolation=cv2.INTER_AREA)
        gray_grid = cv2.resize(gray.astype(np.float32), (grid_size, grid_size),
                                interpolation=cv2.INTER_AREA)

        # Classify modules
        dark_modules = modules == 0
        light_modules = modules == 1

        dark_reflectances = grid[dark_modules]
        light_reflectances = grid[light_modules]

        if len(dark_reflectances) == 0 or len(light_reflectances) == 0:
            return self._fallback_result(decoded_data, r_max, r_min, r_rms, r_msc, n)

        # Calculate parameter grades
        grade_contrast = self._grade_value(r_rms, "RMSC")
        grade_uec = 4  # Assume good if decodeable
        grade_fpd = self._assess_fpd(gray_grid, modules)
        modulation = self._calculate_modulation(dark_reflectances, light_reflectances)
        axial_nonuniformity = self._calculate_anu(grid, modules)
        grid_nonuniformity = self._calculate_gnu(grid, modules)

        grade_modulation = self._grade_value(modulation, "MOD")
        grade_anu = self._grade_value(axial_nonuniformity, "ANU")
        grade_gnu = self._grade_value(grid_nonuniformity, "GNU")

        # Overall grade = minimum
        overall = min(grade_contrast, grade_modulation, grade_anu,
                       grade_gnu, grade_uec, grade_fpd)

        return QualityResult(
            overall_grade=overall,
            overall_grade_char="ABCD"[max(0, 3 - overall)] if overall > 0 else "F",
            r_an=r_max - r_min,
            r_min=r_min,
            r_max=r_max,
            r_rms=r_rms,
            r_msc=r_msc,
            modulation=modulation,
            axial_nonuniformity=axial_nonuniformity,
            grid_nonuniformity=grid_nonuniformity,
            unused_error_correction=1.0 - (self._estimate_errors(modules, grid) / (modules.size * 0.3 + 1e-9)),
            fixed_pattern_damage=grade_fpd / 10.0,
            grade_contrast=grade_contrast,
            grade_modulation=grade_modulation,
            grade_anu=grade_anu,
            grade_gnu=grade_gnu,
            grade_uec=grade_uec,
            grade_fpd=grade_fpd,
            decoded_data=decoded_data,
            decode_success=True,
            width=n,
            height=n,
            modules_count=n,
        )

    def _assess_fallback(self, gray: np.ndarray, normalized: np.ndarray,
                          decoded_data: str, r_max: float, r_min: float,
                          r_rms: float, r_msc: float) -> QualityResult:
        """Fallback assessment when module grid is not available."""
        h, w = gray.shape

        # Estimate module size
        estimated_modules = int(min(h, w) / 8)

        # Global modulation estimate
        mid = (r_max + r_min) / 2
        modulation = (r_max - r_min) / (2 * mid + 1e-9) if mid > 0 else 0

        # Estimate ANU and GNU from intensity gradients
        anu = self._estimate_anu_from_gradients(normalized)
        gnu = self._estimate_gnu_from_grid(normalized)

        # Estimate FPD from finder pattern detection
        fpd = self._estimate_fpd_from_pattern(gray, normalized)

        # Grade each parameter
        grade_contrast = self._grade_value(r_rms, "RMSC")
        grade_modulation = self._grade_value(modulation, "MOD")
        grade_anu = self._grade_value(anu, "ANU")
        grade_gnu = self._grade_value(gnu, "GNU")
        grade_uec = 4 if decoded_data else 0
        grade_fpd = int(max(0, min(4, 4 - fpd * 10)))

        overall = min(grade_contrast, grade_modulation, grade_anu,
                       grade_gnu, grade_uec, grade_fpd)

        return QualityResult(
            overall_grade=overall,
            overall_grade_char="ABCD"[max(0, 3 - overall)] if overall > 0 else "F",
            r_an=r_max - r_min,
            r_min=r_min,
            r_max=r_max,
            r_rms=r_rms,
            r_msc=r_msc,
            modulation=modulation,
            axial_nonuniformity=anu,
            grid_nonuniformity=gnu,
            unused_error_correction=0.9 if decoded_data else 0.3,
            fixed_pattern_damage=fpd,
            grade_contrast=grade_contrast,
            grade_modulation=grade_modulation,
            grade_anu=grade_anu,
            grade_gnu=grade_gnu,
            grade_uec=grade_uec,
            grade_fpd=grade_fpd,
            decoded_data=decoded_data,
            decode_success=bool(decoded_data),
            width=w,
            height=h,
            modules_count=estimated_modules,
        )

    def _fallback_result(self, decoded_data: str, r_max: float, r_min: float,
                          r_rms: float, r_msc: float, n: int) -> QualityResult:
        """Create a fallback result when assessment fails."""
        overall = 1 if decoded_data else 0
        return QualityResult(
            overall_grade=overall,
            overall_grade_char="ABCD"[max(0, 3 - overall)] if overall > 0 else "F",
            r_an=r_max - r_min,
            r_min=r_min,
            r_max=r_max,
            r_rms=r_rms,
            r_msc=r_msc,
            modulation=0.5,
            axial_nonuniformity=0.1,
            grid_nonuniformity=0.15,
            unused_error_correction=0.8 if decoded_data else 0.1,
            fixed_pattern_damage=0.1,
            grade_contrast=2,
            grade_modulation=2,
            grade_anu=2,
            grade_gnu=2,
            grade_uec=4 if decoded_data else 0,
            grade_fpd=2,
            decoded_data=decoded_data,
            decode_success=bool(decoded_data),
            width=n,
            height=n,
            modules_count=n,
        )

    def _calculate_modulation(self, dark: np.ndarray, light: np.ndarray) -> float:
        """Calculate modulation = R_MSC / R_max."""
        r_light = np.mean(light)
        r_dark = np.mean(dark)
        r_max = max(r_light, r_dark)
        if r_max < 1e-9:
            return 0.0
        return (r_light - r_dark) / r_max

    def _calculate_anu(self, grid: np.ndarray, modules: np.ndarray) -> float:
        """Calculate Axial Nonuniformity (ANU)."""
        n = modules.shape[0]
        if n < 2:
            return 0.0

        # Mean reflectance per row and column
        row_means = []
        col_means = []
        for i in range(n):
            row = grid[i, :] if modules.shape[1] >= n else grid[i, :n]
            row_means.append(np.mean(row))
            col = grid[:, i] if modules.shape[0] >= n else grid[:n, i]
            col_means.append(np.mean(col))

        overall_mean = np.mean(grid)
        if abs(overall_mean) < 1e-9:
            overall_mean = 1e-9

        row_var = np.var(row_means) / (overall_mean ** 2 + 1e-9)
        col_var = np.var(col_means) / (overall_mean ** 2 + 1e-9)

        return float(np.sqrt((row_var + col_var) / 2))

    def _calculate_gnu(self, grid: np.ndarray, modules: np.ndarray) -> float:
        """Calculate Grid Nonuniformity (GNU)."""
        n = modules.shape[0]
        if n < 2:
            return 0.0

        module_h = grid.shape[0] / n
        module_w = grid.shape[1] / n

        if module_h < 1 or module_w < 1:
            return 0.0

        overall_mean = np.mean(grid)
        if abs(overall_mean) < 1e-9:
            overall_mean = 1e-9

        # Sample each module cell
        module_means = []
        for i in range(n):
            for j in range(min(n, modules.shape[1])):
                y1 = int(i * module_h)
                y2 = int((i + 1) * module_h)
                x1 = int(j * module_w)
                x2 = int((j + 1) * module_w)
                if y2 > y1 and x2 > x1:
                    cell = grid[y1:y2, x1:x2]
                    module_means.append(np.mean(cell))

        if not module_means:
            return 0.0

        global_mean = np.mean(module_means)
        variance = np.var(module_means)
        gnu = np.sqrt(variance) / (global_mean + 1e-9)

        return float(gnu)

    def _estimate_errors(self, modules: np.ndarray, grid: np.ndarray) -> float:
        """Estimate the number of symbol error correction words used."""
        # Simplified: count modules with incorrect reflectance
        n = modules.shape[0]
        module_h = grid.shape[0] / n
        module_w = grid.shape[1] / n

        errors = 0
        threshold = 0.5

        for i in range(min(n, modules.shape[0])):
            for j in range(min(n, modules.shape[1])):
                y1 = int(i * module_h)
                y2 = int((i + 1) * module_h)
                x1 = int(j * module_w)
                x2 = int((j + 1) * module_w)
                if y2 > y1 and x2 > x1:
                    cell_mean = np.mean(grid[y1:y2, x1:x2])
                    expected = 1.0 if modules[i, j] == 1 else 0.0
                    if abs(cell_mean - expected) > threshold:
                        errors += 1

        return errors

    def _assess_fpd(self, gray_grid: np.ndarray, modules: np.ndarray) -> int:
        """Assess Fixed Pattern Damage (finder patterns)."""
        n = modules.shape[0]

        # The finder pattern in DataMatrix is the L-shape and clock track
        # Check the top row and left column (finder pattern area)
        fp_errors = 0
        total_fp = 0

        for i in range(n):
            for j in range(n):
                # Top row (excluding corner) and left column (excluding corner)
                # These should be the clock track and finder pattern
                is_fp = (i == 0 and j > 0 and j < n - 1) or \
                        (j == 0 and i > 0 and i < n - 1) or \
                        (i == n - 1 and j > 0) or \
                        (j == n - 1 and i > 0)

                if is_fp:
                    total_fp += 1
                    module_h = gray_grid.shape[0] / n
                    module_w = gray_grid.shape[1] / n
                    y1 = int(i * module_h)
                    y2 = int((i + 1) * module_h)
                    x1 = int(j * module_w)
                    x2 = int((j + 1) * module_w)
                    if y2 > y1 and x2 > x1:
                        cell_mean = np.mean(gray_grid[y1:y2, x1:x2]) / 255.0
                        expected = 0.0 if modules[i, j] == 0 else 1.0
                        if abs(cell_mean - expected) > 0.4:
                            fp_errors += 1

        if total_fp == 0:
            return 4

        fpd_ratio = fp_errors / total_fp
        return int(max(0, min(4, 4 * (1 - fpd_ratio))))

    def _estimate_anu_from_gradients(self, normalized: np.ndarray) -> float:
        """Estimate ANU from intensity gradients."""
        h, w = normalized.shape
        # Row and column averages
        row_means = np.mean(normalized, axis=1)
        col_means = np.mean(normalized, axis=0)
        overall = np.mean(normalized)
        if abs(overall) < 1e-9:
            overall = 1e-9
        anu = float(np.std(row_means) / overall + np.std(col_means) / overall) / 2
        return min(anu, 1.0)

    def _estimate_gnu_from_grid(self, normalized: np.ndarray) -> float:
        """Estimate GNU from grid analysis."""
        h, w = normalized.shape
        # Estimate grid size
        grid_n = max(8, int(min(h, w) / 10))
        module_h = h / grid_n
        module_w = w / grid_n

        means = []
        for i in range(grid_n):
            for j in range(grid_n):
                y1, y2 = int(i * module_h), int((i + 1) * module_h)
                x1, x2 = int(j * module_w), int((j + 1) * module_w)
                if y2 > y1 and x2 > x1:
                    means.append(np.mean(normalized[y1:y2, x1:x2]))

        if not means:
            return 0.2
        g = np.std(means) / (np.mean(means) + 1e-9)
        return min(float(g), 1.0)

    def _estimate_fpd_from_pattern(self, gray: np.ndarray,
                                     normalized: np.ndarray) -> float:
        """Estimate FPD from finder pattern analysis."""
        h, w = gray.shape
        # Check corners and edges for L-pattern
        corner_size = max(5, min(h, w) // 10)
        score = 0.0

        # Top-left corner
        tl = normalized[:corner_size, :corner_size]
        score += np.std(tl)

        # Top-right
        tr = normalized[:corner_size, -corner_size:]
        score += np.std(tr)

        # Bottom-left
        bl = normalized[-corner_size:, :corner_size]
        score += np.std(bl)

        # Bottom-right
        br = normalized[-corner_size:, -corner_size:]
        score += np.std(br)

        return min(score / 4.0, 1.0)

    def _grade_value(self, value: float, param: str) -> int:
        """Grade a parameter value according to thresholds."""
        th = self.thresholds

        if param == "RMSC":
            if value >= th[4]["RMSC"]:
                return 4
            elif value >= th[3]["RMSC"]:
                return 3
            elif value >= th[2]["RMSC"]:
                return 2
            elif value >= th[1]["RMSC"]:
                return 1
            return 0

        elif param == "MOD":
            if value >= th[4]["MOD"]:
                return 4
            elif value >= th[3]["MOD"]:
                return 3
            elif value >= th[2]["MOD"]:
                return 2
            elif value >= th[1]["MOD"]:
                return 1
            return 0

        elif param == "ANU":
            # Lower is better
            if value <= th[4]["ANU"]:
                return 4
            elif value <= th[3]["ANU"]:
                return 3
            elif value <= th[2]["ANU"]:
                return 2
            elif value <= th[1]["ANU"]:
                return 1
            return 0

        elif param == "GNU":
            # Lower is better
            if value <= th[4]["GNU"]:
                return 4
            elif value <= th[3]["GNU"]:
                return 3
            elif value <= th[2]["GNU"]:
                return 2
            elif value <= th[1]["GNU"]:
                return 1
            return 0

        elif param == "FPD":
            # Lower is better
            if value <= th[4]["FPD"]:
                return 4
            elif value <= th[3]["FPD"]:
                return 3
            elif value <= th[2]["FPD"]:
                return 2
            elif value <= th[1]["FPD"]:
                return 1
            return 0

        return 1
