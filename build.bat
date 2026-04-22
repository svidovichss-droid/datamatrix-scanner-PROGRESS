@echo off
chcp 65001 > nul
echo ═══════════════════════════════════════════════════════════════
echo   DataMatrix Scanner - Сборка EXE
echo   Авторы: А. Свидович / А. Петляков для PROGRESS
echo ═══════════════════════════════════════════════════════════════
echo.

:: Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден. Установите Python 3.10+ с python.org
    pause
    exit /b 1
)

:: Check pip
pip --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] pip не найден
    pause
    exit /b 1
)

echo [1/4] Проверка зависимостей...
pip install --quiet pip --upgrade
if errorlevel 1 (
    echo [ОШИБКА] Не удалось обновить pip
    pause
    exit /b 1
)

echo [2/4] Установка зависимостей...
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости
    echo Попробуйте: pip install PyQt5 opencv-python pylibdmtx pyinstaller
    pause
    exit /b 1
)

echo [3/4] Сборка EXE с PyInstaller...
cd /d "%~dp0"
pyinstaller datamatrix_scanner.spec --clean --noconfirm
if errorlevel 1 (
    echo [ОШИБКА] PyInstaller failed
    pause
    exit /b 1
)

echo [4/4] Проверка результата...
if exist "dist\DataMatrixScanner\DataMatrixScanner.exe" (
    echo.
    echo ═══════════════════════════════════════════════════════════════
    echo   СБОРКА УСПЕШНА!
    echo   EXE: dist\DataMatrixScanner\DataMatrixScanner.exe
    echo   Размер: %~z0
    echo ═══════════════════════════════════════════════════════════════
) else (
    echo [ОШИБКА] EXE не найден после сборки
    dir /s /b dist\*.exe 2>nul
)

echo.
echo Запуск DataMatrixScanner.exe...
start "" "dist\DataMatrixScanner\DataMatrixScanner.exe"
pause
