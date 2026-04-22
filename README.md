# DataMatrix Scanner — Сканер качества печати DataMatrix

**ГОСТ Р 57302-2016**

**Авторы:** А. Свидович / А. Петляков для PROGRESS

---

## Описание

Профессиональный сканер качества печати двумерных штрихкодов DataMatrix, разработанный для интеграции с промышленными камерами на конвейерных линиях. Приложение выполняет непрерывный поиск и автоматическую оценку качества печати DataMatrix кодов в соответствии с ГОСТ Р 57302-2016 (эквивалент ISO/IEC 15415).

---

## Возможности

- **Непрерывный поиск** — режим реального времени с захватом любых квадратов и валидацией DataMatrix
- **Оценка качества** по 6 параметрам ГОСТ Р 57302-2016:
  - Контраст символа (RMSC) — оценка A–F
  - Модуляция (MOD) — оценка A–F
  - Осевая неравномерность (ANU) — оценка A–F
  - Сеточная неравномерность (GNU) — оценка A–F
  - Неиспользованная коррекция ошибок (UEC) — оценка A–F
  - Повреждение шаблона (FPD) — оценка A–F
  - **Итоговая оценка** = минимум всех параметров (0–4, F–A)
- **История сканирований** — SQLite база данных с фильтрацией по оценке
- **Статистика** — распределение оценок, процент годных, средние значения
- **Декодирование** — распознавание данных DataMatrix с pylibdmtx
- **Экспорт результатов** — журнал событий в реальном времени

---

## Требования

### Системные требования
- **ОС:** Windows 10/11 x64 (для EXE сборки)
- **Камера:** Любая промышленная камера с поддержкой DirectShow
- **Разрешение камеры:** рекомендуется 1920×1080 или выше

### Сборка из исходников
- Python 3.10+
- см. `requirements.txt`

---

## Быстрый старт

### 1. Скачать готовый EXE
Скачайте последний релиз со страницы [Releases](https://github.com/YOUR_REPO/releases).

### 2. Собрать из исходников

```bash
# Клонировать репозиторий
git clone https://github.com/YOUR_REPO/datamatrix-scanner.git
cd datamatrix_scanner

# Установить зависимости
pip install -r requirements.txt

# Собрать EXE (Windows)
pyinstaller datamatrix_scanner.spec --clean --noconfirm

# Или запустите build.bat (Windows)
```

### 3. Запуск
```
dist\DataMatrixScanner\DataMatrixScanner.exe
```

---

## Сборка на GitHub Actions

Репозиторий настроен для автоматической сборки EXE при пуше в `main` или создании тега `v*`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions автоматически:
1. Установит Python 3.11 на Windows runner
2. Установит зависимости
3. Соберёт EXE через PyInstaller
4. Создаст zip-архив
5. Опубликует релиз (при теге)

---

## Структура проекта

```
datamatrix_scanner/
├── src/
│   ├── main.py          # Точка входа
│   ├── config.py        # Конфигурация
│   ├── camera.py        # Захват видео с камеры
│   ├── detector.py      # Детекция DataMatrix / квадратов
│   ├── quality.py        # Оценка качества ГОСТ Р 57302-2016
│   ├── database.py      # SQLite хранилище истории
│   ├── scanner.py       # Основной движок сканирования
│   └── ui.py            # Графический интерфейс PyQt5
├── icons/
├── .github/workflows/
│   └── build.yml        # GitHub Actions workflow
├── requirements.txt     # Python зависимости
├── build.bat            # Скрипт сборки для Windows
├── datamatrix_scanner.spec  # PyInstaller спецификация
├── version_info.txt     # Windows version info
└── README.md
```

---

## Настройка

Все параметры редактируются в файле `src/config.json`:

```json
{
    "CAMERA_INDEX": 0,          # Индекс камеры (0 = первая)
    "CAMERA_WIDTH": 1920,        # Ширина кадра
    "CAMERA_HEIGHT": 1080,       # Высота кадра
    "CAMERA_FPS": 30,            # FPS камеры
    "SCAN_INTERVAL_MS": 100,     # Интервал сканирования (мс)
    "SQUARE_MIN_SIZE": 20,       # Мин. размер квадрата (пикс.)
    "HISTORY_LIMIT": 500         # Макс. записей истории
}
```

---

## Шкала оценок (ГОСТ Р 57302-2016)

| Оценка | Баллы | Описание |
|--------|-------|----------|
| **A**   | 4     | Отлично — годен для любого применения |
| **B**   | 3     | Хорошо — приемлемо для большинства задач |
| **C**   | 2     | Удовлетворительно — ограниченное применение |
| **D**   | 1     | Плохо — высокий риск ошибок считывания |
| **F**   | 0     | Неудовлетворительно — считывание невозможно |

**Итоговая оценка** = минимальная из всех 6 параметров.

---

## Параметры качества

| Параметр | Описание | Метод |
|----------|----------|-------|
| **RMSC** | Контраст символа (Root Mean Square) | `(R_max - R_min) / (R_max + R_min)` |
| **MOD**  | Модуляция = R_MSC / R_max | Отношение контраста края к макс. яркости |
| **ANU**  | Осевая неравномерность | Отклонение яркости по осям |
| **GNU**  | Сеточная неравномерность | Отклонение яркости модулей |
| **UEC**  | Неиспользованная коррекция ошибок | Доля неисп. кодовых слов EC |
| **FPD**  | Повреждение шаблона | Ошибки в finder pattern |

---

## Примечания

- При отсутствии `pylibdmtx` приложение использует структурный анализ для детекции DataMatrix
- Для промышленного применения рекомендуется камера с высоким разрешением и стабильным освещением
- База данных (`datamatrix_scanner.db`) создаётся автоматически в каталоге запуска

---

---

## 📦 Сборка под Windows

### Вариант 1: Автоматическая сборка через GitHub Actions (Рекомендуется)

1. **Запушьте изменения** в ветку `main` или `master`
2. **Или создайте тег версии**: `git tag v1.0.0 && git push origin v1.0.0`
3. Перейдите на вкладку **Actions** в вашем репозитории на GitHub
4. Выберите последний запуск **"Build DataMatrix Scanner EXE"**
5. Скачайте артефакт **`DataMatrixScanner-win64.zip`** из раздела "Artifacts"

Готовый EXE файл будет доступен для скачивания в течение 30 дней.

---

### Вариант 2: Локальная сборка на Windows

#### Требования:
- **Windows 10/11 x64**
- **Python 3.10 - 3.12** (скачать с [python.org](https://www.python.org/downloads/))
- **Visual C++ Redistributable** (обычно устанавливается с Python)

#### Пошаговая инструкция:

1. **Откройте PowerShell или Command Prompt от имени администратора**

2. **Установите зависимости:**
   ```bat
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. **Проверьте установку библиотек:**
   ```bat
   python -c "import cv2; print(f'OpenCV: {cv2.__version__}')"
   python -c "import pylibdmtx; print('pylibdmtx: OK')"
   ```

4. **Запустите сборку:**
   ```bat
   build.bat
   ```
   
   **Или вручную через PyInstaller:**
   ```bat
   pyinstaller datamatrix_scanner.spec --clean --noconfirm
   ```

5. **Готовый файл** будет находиться в папке:
   ```
   dist\DataMatrixScanner\DataMatrixScanner.exe
   ```

---

### 🔧 Решение проблем при сборке

#### Ошибка: `ModuleNotFoundError: No module named 'cv2'`
```bat
pip uninstall opencv-python
pip install opencv-python --force-reinstall
```

#### Ошибка: `ModuleNotFoundError: No module named 'pylibdmtx'`
```bat
pip install pylibdmtx==0.8.5
```

#### Ошибка: `libdmtx not found` (требуется для pylibdmtx)
Установите предварительно скомпилированную версию:
```bat
pip install pylibdmtx --only-binary :all:
```

#### Ошибка при сборке с иконкой
Убедитесь, что файл `icons\app.ico` существует. Если нет - удалите строку `icon='icons\\app.ico'` из файла `datamatrix_scanner.spec`

---

### 📁 Структура дистрибутива

После успешной сборки вы получите:
```
dist/DataMatrixScanner/
├── DataMatrixScanner.exe    # Основной исполняемый файл
├── *.dll                     # Библиотеки
├── src/
│   └── config.json          # Файл конфигурации
└── _internal/               # Внутренние файлы PyInstaller
```

---

## Лицензия

MIT License — см. файл [LICENSE](LICENSE)

Авторские права: А. Свидович / А. Петляков для PROGRESS
