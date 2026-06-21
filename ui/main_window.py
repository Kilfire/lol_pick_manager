"""
Главное окно приложения LoL Picks Manager.
"""
import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QSplitter, QStatusBar, QMenuBar, QMenu, QInputDialog,
    QFileDialog, QMessageBox, QFrame, QToolBar, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QFont, QColor

from core.models import Preset, Champion, get_example_presets
from core.google_sheets import sheets_manager
from ui.champion_table import ChampionTable
from ui.champion_dialog import ChampionDialog
from ui.google_dialog import GoogleSheetsDialog

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS_DIR = os.path.join(BASE_DIR, "presets")


class _AutoConnectWorker(QThread):
    """Подключается к Google Sheets в фоновом потоке при старте программы,
    чтобы не блокировать интерфейс на время сетевого запроса."""
    done = pyqtSignal(bool, str)

    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def run(self):
        ok, msg = self._manager.connect()
        self.done.emit(ok, msg)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Picks Manager  •  Tournament Tool")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 780)

        self._presets: list[Preset] = []
        self._current_preset: Preset | None = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()

        self._load_local_presets()
        self._try_auto_connect_google()

    # ── Меню ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # Файл
        fileMenu = mb.addMenu("Файл")
        actNewPreset = QAction("Новый пресет", self)
        actNewPreset.setShortcut("Ctrl+N")
        actNewPreset.triggered.connect(self._new_preset)
        fileMenu.addAction(actNewPreset)

        actSaveLocal = QAction("Сохранить пресет (JSON)", self)
        actSaveLocal.setShortcut("Ctrl+S")
        actSaveLocal.triggered.connect(self._save_current_local)
        fileMenu.addAction(actSaveLocal)

        actLoadLocal = QAction("Открыть пресет (JSON)...", self)
        actLoadLocal.setShortcut("Ctrl+O")
        actLoadLocal.triggered.connect(self._load_local_file)
        fileMenu.addAction(actLoadLocal)

        fileMenu.addSeparator()
        actQuit = QAction("Выход", self)
        actQuit.setShortcut("Ctrl+Q")
        actQuit.triggered.connect(self.close)
        fileMenu.addAction(actQuit)

        # Google
        cloudMenu = mb.addMenu("☁ Google Sheets")
        actGoogleDialog = QAction("Управление Google Sheets...", self)
        actGoogleDialog.triggered.connect(self._open_google_dialog)
        cloudMenu.addAction(actGoogleDialog)

        actSaveGoogle = QAction("Сохранить текущий пресет → Sheets", self)
        actSaveGoogle.triggered.connect(self._save_current_google)
        cloudMenu.addAction(actSaveGoogle)

        # Чемпионы
        champMenu = mb.addMenu("Чемпионы")
        actAdd = QAction("Добавить чемпиона", self)
        actAdd.setShortcut("Ctrl+A")
        actAdd.triggered.connect(self._add_champion)
        champMenu.addAction(actAdd)

        # Справка
        helpMenu = mb.addMenu("Справка")
        actAbout = QAction("О программе", self)
        actAbout.triggered.connect(self._show_about)
        helpMenu.addAction(actAbout)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        mainLayout = QVBoxLayout(central)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # ── Верхняя полоса ────────────────────────────────────────────────────
        topBar = QWidget()
        topBar.setObjectName("topBar")
        topBar.setFixedHeight(52)
        topLayout = QHBoxLayout(topBar)
        topLayout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("⚔  LoL Picks Manager")
        title.setObjectName("appTitle")
        topLayout.addWidget(title)
        topLayout.addStretch()

        # Google status
        self.lblGoogleStatus = QLabel("☁ Не подключено")
        self.lblGoogleStatus.setStyleSheet("color: #6A7A8A; font-size: 11px;")
        topLayout.addWidget(self.lblGoogleStatus)

        btnGoogle = QPushButton("☁ Google Sheets")
        btnGoogle.setObjectName("btnGoogle")
        btnGoogle.clicked.connect(self._open_google_dialog)
        topLayout.addWidget(btnGoogle)

        mainLayout.addWidget(topBar)

        # ── Основное содержимое ───────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Левая панель: список пресетов ─────────────────────────────────────
        leftPanel = QWidget()
        leftPanel.setObjectName("sidePanel")
        leftLayout = QVBoxLayout(leftPanel)
        leftLayout.setContentsMargins(10, 12, 10, 12)
        leftLayout.setSpacing(8)

        lblPresets = QLabel("ПРЕСЕТЫ")
        lblPresets.setObjectName("sectionTitle")
        leftLayout.addWidget(lblPresets)

        self.listPresets = QListWidget()
        self.listPresets.setObjectName("presetList")
        self.listPresets.currentRowChanged.connect(self._on_preset_selected)
        leftLayout.addWidget(self.listPresets, 1)

        # Кнопки пресетов
        for text, slot in [
            ("+ Новый пресет",    self._new_preset),
            ("📂 Загрузить JSON", self._load_local_file),
            ("💾 Сохранить JSON", self._save_current_local),
            ("☁ Сохранить→Sheets", self._save_current_google),
            ("✕ Удалить пресет", self._delete_current_preset),
        ]:
            btn = QPushButton(text)
            if "Удалить" in text:
                btn.setObjectName("btnDanger")
            leftLayout.addWidget(btn)
            btn.clicked.connect(slot)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1E2A3A;")
        leftLayout.addWidget(sep)

        # Инфо о текущем пресете
        lblInfo = QLabel("ИНФО")
        lblInfo.setObjectName("sectionTitle")
        leftLayout.addWidget(lblInfo)

        self.lblPresetName  = QLabel("—")
        self.lblPresetType  = QLabel("—")
        self.lblChampCount  = QLabel("Чемпионов: 0")

        for lbl in [self.lblPresetName, self.lblPresetType, self.lblChampCount]:
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #8A9AB0; font-size: 11px;")
            leftLayout.addWidget(lbl)

        splitter.addWidget(leftPanel)

        # ── Правая панель: таблица ────────────────────────────────────────────
        rightPanel = QWidget()
        rightLayout = QVBoxLayout(rightPanel)
        rightLayout.setContentsMargins(12, 12, 12, 8)
        rightLayout.setSpacing(10)

        # Заголовок + кнопка добавления
        headerRow = QHBoxLayout()
        self.lblTableTitle = QLabel("Выберите пресет")
        self.lblTableTitle.setObjectName("sectionTitle")
        headerRow.addWidget(self.lblTableTitle)
        headerRow.addStretch()

        btnAdd = QPushButton("+ Добавить чемпиона")
        btnAdd.setObjectName("btnSuccess")
        btnAdd.clicked.connect(self._add_champion)
        headerRow.addWidget(btnAdd)
        rightLayout.addLayout(headerRow)

        # Таблица
        self.champTable = ChampionTable()
        self.champTable.editRequested.connect(self._edit_champion)
        self.champTable.deleteRequested.connect(self._delete_champion)
        rightLayout.addWidget(self.champTable, 1)

        splitter.addWidget(rightPanel)
        splitter.setSizes([220, 900])
        splitter.setHandleWidth(2)

        mainLayout.addWidget(splitter, 1)

    def _build_statusbar(self):
        self.statusBar().showMessage("Готово  |  LoL Picks Manager")

    # ── Пресеты ───────────────────────────────────────────────────────────────

    def _load_local_presets(self):
        """При старте загружает пресеты из папки presets/ или примеры."""
        loaded = False
        if os.path.isdir(PRESETS_DIR):
            for fn in sorted(os.listdir(PRESETS_DIR)):
                if fn.endswith(".json"):
                    try:
                        preset = Preset.load_local(os.path.join(PRESETS_DIR, fn))
                        self._presets.append(preset)
                        loaded = True
                    except Exception:
                        pass

        if not loaded:
            # Добавляем демо-пресеты
            self._presets = get_example_presets()
            for p in self._presets:
                p.save_local(PRESETS_DIR)

        self._refresh_preset_list()
        if self._presets:
            self.listPresets.setCurrentRow(0)

    def _refresh_preset_list(self):
        self.listPresets.clear()
        for preset in self._presets:
            item = QListWidgetItem(preset.name)
            color = "#C8AA6E" if preset.team_type == "Наша команда" else "#E74C3C"
            item.setForeground(QColor(color))
            # Иконка команды
            icon_text = "🔵" if preset.team_type == "Наша команда" else "🔴"
            item.setText(f"{icon_text} {preset.name}")
            self.listPresets.addItem(item)

    def _on_preset_selected(self, row: int):
        if row < 0 or row >= len(self._presets):
            return
        self._current_preset = self._presets[row]
        self.champTable.set_champions(self._current_preset.champions)
        self.lblTableTitle.setText(
            f"{self._current_preset.name}  [{self._current_preset.team_type}]")
        self.lblPresetName.setText(f"📋 {self._current_preset.name}")
        self.lblPresetType.setText(f"🏆 {self._current_preset.team_type}")
        self.lblChampCount.setText(
            f"Чемпионов: {len(self._current_preset.champions)}")
        self.statusBar().showMessage(
            f"Пресет: {self._current_preset.name}  •  "
            f"{len(self._current_preset.champions)} чемпионов")

    def _new_preset(self):
        name, ok = QInputDialog.getText(self, "Новый пресет", "Название пресета:")
        if not ok or not name.strip():
            return
        team, ok2 = QInputDialog.getItem(
            self, "Тип команды", "Выберите тип:",
            ["Наша команда", "Противники"], 0, False)
        if not ok2:
            return
        preset = Preset(name=name.strip(), team_type=team)
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)
        self.statusBar().showMessage(f"Создан новый пресет: {preset.name}")

    def _save_current_local(self):
        if not self._current_preset:
            QMessageBox.warning(self, "Нет пресета", "Сначала выберите пресет.")
            return
        path = self._current_preset.save_local(PRESETS_DIR)
        self.statusBar().showMessage(f"Сохранено: {path}")
        QMessageBox.information(self, "Сохранено",
                                f"Пресет сохранён:\n{path}")

    def _load_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть пресет", PRESETS_DIR, "JSON (*.json)")
        if not path:
            return
        try:
            preset = Preset.load_local(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить:\n{e}")
            return
        # Проверяем, не загружен ли уже
        for i, p in enumerate(self._presets):
            if p.name == preset.name:
                self._presets[i] = preset
                self._refresh_preset_list()
                self.listPresets.setCurrentRow(i)
                self.statusBar().showMessage(f"Обновлён: {preset.name}")
                return
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)
        self.statusBar().showMessage(f"Загружен: {preset.name}")

    def _delete_current_preset(self):
        if not self._current_preset:
            return
        reply = QMessageBox.question(
            self, "Удалить пресет",
            f"Удалить «{self._current_preset.name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._presets.remove(self._current_preset)
            self._current_preset = None
            self._refresh_preset_list()
            self.champTable.set_champions([])
            self.lblTableTitle.setText("Выберите пресет")

    # ── Google Sheets ──────────────────────────────────────────────────────────

    def _try_auto_connect_google(self):
        """Если service_account.json и ID таблицы уже настроены (например,
        капитан прислал готовую конфигурацию), пробуем подключиться сразу
        при запуске — без нажатия каких-либо кнопок пользователем."""
        if not sheets_manager.has_service_account_file():
            return
        if not sheets_manager.get_spreadsheet_id():
            return

        self.statusBar().showMessage("Подключение к Google Sheets...")
        self._autoconnect_worker = _AutoConnectWorker(sheets_manager)
        self._autoconnect_worker.done.connect(self._on_auto_connect_done)
        self._autoconnect_worker.start()

    def _on_auto_connect_done(self, ok: bool, msg: str):
        self._update_google_status()
        if ok:
            self.statusBar().showMessage(f"☁ {msg}")
        else:
            self.statusBar().showMessage(f"☁ Не удалось подключиться: {msg}")

    def _open_google_dialog(self):
        dlg = GoogleSheetsDialog(self)
        dlg.presetLoaded.connect(self._load_from_google)
        dlg.exec()
        self._update_google_status()

    def _update_google_status(self):
        if sheets_manager.is_connected():
            self.lblGoogleStatus.setText("☁ Подключено к Sheets")
            self.lblGoogleStatus.setStyleSheet("color: #2ECC71; font-size: 11px;")
        else:
            self.lblGoogleStatus.setText("☁ Не подключено")
            self.lblGoogleStatus.setStyleSheet("color: #6A7A8A; font-size: 11px;")

    def _save_current_google(self):
        if not self._current_preset:
            QMessageBox.warning(self, "Нет пресета", "Сначала выберите пресет.")
            return
        if not sheets_manager.is_connected():
            QMessageBox.information(
                self, "Не подключено",
                "Сначала подключитесь к Google Sheets через меню ☁")
            self._open_google_dialog()
            return
        ok, msg = sheets_manager.save_preset(self._current_preset)
        if ok:
            QMessageBox.information(self, "Сохранено", msg)
        else:
            QMessageBox.critical(self, "Ошибка", msg)
        self.statusBar().showMessage(msg)

    def _load_from_google(self, preset_name: str):
        if not sheets_manager.is_connected():
            return
        preset, msg = sheets_manager.load_preset(preset_name)
        if preset is None:
            QMessageBox.critical(self, "Ошибка", msg)
            return
        # Обновляем или добавляем
        for i, p in enumerate(self._presets):
            if p.name == preset.name:
                self._presets[i] = preset
                self._refresh_preset_list()
                self.listPresets.setCurrentRow(i)
                self.statusBar().showMessage(f"Загружен из Sheets: {preset.name}")
                return
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)
        self.statusBar().showMessage(f"Загружен из Sheets: {preset.name}  •  {msg}")

    # ── Чемпионы ──────────────────────────────────────────────────────────────

    def _add_champion(self):
        if not self._current_preset:
            QMessageBox.warning(self, "Нет пресета",
                                "Сначала создайте или выберите пресет.")
            return
        dlg = ChampionDialog(parent=self)
        if dlg.exec():
            champ = dlg.get_champion()
            self._current_preset.champions.append(champ)
            self.champTable.set_champions(self._current_preset.champions)
            self.lblChampCount.setText(
                f"Чемпионов: {len(self._current_preset.champions)}")
            self.statusBar().showMessage(f"Добавлен: {champ.name}")

    def _edit_champion(self, idx: int):
        if not self._current_preset:
            return
        champ = self._current_preset.champions[idx]
        dlg = ChampionDialog(champ, parent=self)
        if dlg.exec():
            updated = dlg.get_champion()
            self._current_preset.champions[idx] = updated
            self.champTable.set_champions(self._current_preset.champions)
            self.statusBar().showMessage(f"Обновлён: {updated.name}")

    def _delete_champion(self, idx: int):
        if not self._current_preset:
            return
        champ = self._current_preset.champions[idx]
        reply = QMessageBox.question(
            self, "Удалить чемпиона",
            f"Удалить «{champ.name}» из пресета?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._current_preset.champions.pop(idx)
            self.champTable.set_champions(self._current_preset.champions)
            self.lblChampCount.setText(
                f"Чемпионов: {len(self._current_preset.champions)}")
            self.statusBar().showMessage(f"Удалён: {champ.name}")

    # ── Справка ───────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            "<b>LoL Picks Manager</b><br>"
            "Инструмент для управления пиками на турнирах по League of Legends<br><br>"
            "Функции:<br>"
            "• Управление пресетами чемпионов для разных команд<br>"
            "• Роль (Топ/Лес/Мид/Адк/Сап) и класс урона (АД/АП/Танк/Утилити/Гибрид)<br>"
            "• Фильтрация по роли, классу урона, тиру и имени<br>"
            "• Сортировка по роли → классу урона → тиру<br>"
            "• Сохранение в JSON (локально) и Google Sheets (облако, общий доступ)<br>"
            "• Иконки чемпионов и предметов<br>"
            "• Основной и ситуативный билды<br><br>"
            "Иконки чемпионов: <code>icons/champions/ИМЯ.png</code><br>"
            "Иконки предметов: <code>icons/items/ИМЯ.png</code><br><br>"
            "Облачная синхронизация использует сервисный аккаунт Google "
            "(<code>service_account.json</code>) — без браузерной авторизации."
        )

    def closeEvent(self, event):
        # Автосохранение всех пресетов
        for preset in self._presets:
            try:
                preset.save_local(PRESETS_DIR)
            except Exception:
                pass
        event.accept()
