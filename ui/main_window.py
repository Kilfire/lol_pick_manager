"""
Главное окно приложения LoL Picks Manager.
Поддерживает переключение языка интерфейса (RU/EN) через переключатель
в верхней панели.
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

from core.models import Preset, Champion, get_example_presets, team_type_display, TEAM_TYPE_DISPLAY_KEYS
from core.google_sheets import sheets_manager
from core.i18n import tr, lang_manager
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
        self.setMinimumSize(1100, 700)
        self.resize(1300, 780)

        self._presets: list[Preset] = []
        self._current_preset: Preset | None = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()

        # Синхронизируем переключатель языка с сохранённым значением (без
        # повторного срабатывания currentIndexChanged, чтобы не дёргать
        # set_language лишний раз на старте)
        self.comboLanguage.blockSignals(True)
        idx = self.comboLanguage.findData(lang_manager.get_language())
        if idx >= 0:
            self.comboLanguage.setCurrentIndex(idx)
        self.comboLanguage.blockSignals(False)

        self.retranslate_ui()
        lang_manager.add_listener(self.retranslate_ui)

        self._load_local_presets()
        self._try_auto_connect_google()

    # ── Меню ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # Файл
        self.fileMenu = mb.addMenu("")
        self.actNewPreset = QAction(self)
        self.actNewPreset.setShortcut("Ctrl+N")
        self.actNewPreset.triggered.connect(self._new_preset)
        self.fileMenu.addAction(self.actNewPreset)

        self.actSaveLocal = QAction(self)
        self.actSaveLocal.setShortcut("Ctrl+S")
        self.actSaveLocal.triggered.connect(self._save_current_local)
        self.fileMenu.addAction(self.actSaveLocal)

        self.actLoadLocal = QAction(self)
        self.actLoadLocal.setShortcut("Ctrl+O")
        self.actLoadLocal.triggered.connect(self._load_local_file)
        self.fileMenu.addAction(self.actLoadLocal)

        self.fileMenu.addSeparator()
        self.actQuit = QAction(self)
        self.actQuit.setShortcut("Ctrl+Q")
        self.actQuit.triggered.connect(self.close)
        self.fileMenu.addAction(self.actQuit)

        # Google
        self.cloudMenu = mb.addMenu("")
        self.actGoogleDialog = QAction(self)
        self.actGoogleDialog.triggered.connect(self._open_google_dialog)
        self.cloudMenu.addAction(self.actGoogleDialog)

        self.actSaveGoogle = QAction(self)
        self.actSaveGoogle.triggered.connect(self._save_current_google)
        self.cloudMenu.addAction(self.actSaveGoogle)

        # Чемпионы
        self.champMenu = mb.addMenu("")
        self.actAdd = QAction(self)
        self.actAdd.setShortcut("Ctrl+A")
        self.actAdd.triggered.connect(self._add_champion)
        self.champMenu.addAction(self.actAdd)

        # Справка
        self.helpMenu = mb.addMenu("")
        self.actAbout = QAction(self)
        self.actAbout.triggered.connect(self._show_about)
        self.helpMenu.addAction(self.actAbout)

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

        self.lblTitle = QLabel()
        self.lblTitle.setObjectName("appTitle")
        topLayout.addWidget(self.lblTitle)
        topLayout.addStretch()

        # ── Переключатель языка ─────────────────────────────────────────────
        self.lblLanguage = QLabel()
        self.lblLanguage.setStyleSheet("color: #6A7A8A; font-size: 11px;")
        topLayout.addWidget(self.lblLanguage)

        self.comboLanguage = QComboBox()
        self.comboLanguage.addItem("Русский", "ru")
        self.comboLanguage.addItem("English", "en")
        self.comboLanguage.setFixedWidth(110)
        self.comboLanguage.currentIndexChanged.connect(self._on_language_changed)
        topLayout.addWidget(self.comboLanguage)

        # Google status
        self.lblGoogleStatus = QLabel()
        self.lblGoogleStatus.setStyleSheet("color: #6A7A8A; font-size: 11px;")
        topLayout.addWidget(self.lblGoogleStatus)

        self.btnGoogle = QPushButton()
        self.btnGoogle.setObjectName("btnGoogle")
        self.btnGoogle.clicked.connect(self._open_google_dialog)
        topLayout.addWidget(self.btnGoogle)

        mainLayout.addWidget(topBar)

        # ── Основное содержимое ───────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Левая панель: список пресетов ─────────────────────────────────────
        leftPanel = QWidget()
        leftPanel.setObjectName("sidePanel")
        leftLayout = QVBoxLayout(leftPanel)
        leftLayout.setContentsMargins(10, 12, 10, 12)
        leftLayout.setSpacing(8)

        self.lblPresetsTitle = QLabel()
        self.lblPresetsTitle.setObjectName("sectionTitle")
        leftLayout.addWidget(self.lblPresetsTitle)

        self.listPresets = QListWidget()
        self.listPresets.setObjectName("presetList")
        self.listPresets.currentRowChanged.connect(self._on_preset_selected)
        leftLayout.addWidget(self.listPresets, 1)

        # Кнопки пресетов
        self.btnNewPreset   = QPushButton()
        self.btnLoadJson    = QPushButton()
        self.btnSaveJson    = QPushButton()
        self.btnSaveSheets  = QPushButton()
        self.btnDeletePreset = QPushButton()
        self.btnDeletePreset.setObjectName("btnDanger")

        for btn, slot in [
            (self.btnNewPreset,    self._new_preset),
            (self.btnLoadJson,     self._load_local_file),
            (self.btnSaveJson,     self._save_current_local),
            (self.btnSaveSheets,   self._save_current_google),
            (self.btnDeletePreset, self._delete_current_preset),
        ]:
            leftLayout.addWidget(btn)
            btn.clicked.connect(slot)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1E2A3A;")
        leftLayout.addWidget(sep)

        # Инфо о текущем пресете
        self.lblInfoTitle = QLabel()
        self.lblInfoTitle.setObjectName("sectionTitle")
        leftLayout.addWidget(self.lblInfoTitle)

        self.lblPresetName  = QLabel("—")
        self.lblPresetType  = QLabel("—")
        self.lblChampCount  = QLabel()

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
        self.lblTableTitle = QLabel()
        self.lblTableTitle.setObjectName("sectionTitle")
        headerRow.addWidget(self.lblTableTitle)
        headerRow.addStretch()

        self.btnAddChampion = QPushButton()
        self.btnAddChampion.setObjectName("btnSuccess")
        self.btnAddChampion.clicked.connect(self._add_champion)
        headerRow.addWidget(self.btnAddChampion)
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
        self.statusBar().showMessage("")

    # ── Перевод ───────────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self.setWindowTitle("LoL Picks Manager  •  Tournament Tool")

        # Меню
        self.fileMenu.setTitle(tr("menu_file"))
        self.actNewPreset.setText(tr("menu_new_preset"))
        self.actSaveLocal.setText(tr("menu_save_local"))
        self.actLoadLocal.setText(tr("menu_load_local"))
        self.actQuit.setText(tr("menu_quit"))

        self.cloudMenu.setTitle(tr("menu_cloud"))
        self.actGoogleDialog.setText(tr("menu_cloud_manage"))
        self.actSaveGoogle.setText(tr("menu_cloud_save"))

        self.champMenu.setTitle(tr("menu_champions"))
        self.actAdd.setText(tr("menu_add_champion"))

        self.helpMenu.setTitle(tr("menu_help"))
        self.actAbout.setText(tr("menu_about"))

        # Верхняя панель
        self.lblTitle.setText(tr("app_title"))
        self.lblLanguage.setText(tr("language"))
        self.btnGoogle.setText(tr("menu_cloud"))
        self._update_google_status()

        # Левая панель
        self.lblPresetsTitle.setText(tr("presets_title"))
        self.btnNewPreset.setText(tr("btn_new_preset"))
        self.btnLoadJson.setText(tr("btn_load_json"))
        self.btnSaveJson.setText(tr("btn_save_json"))
        self.btnSaveSheets.setText(tr("btn_save_sheets"))
        self.btnDeletePreset.setText(tr("btn_delete_preset"))
        self.lblInfoTitle.setText(tr("info_title"))

        if self._current_preset:
            self.lblChampCount.setText(
                tr("champ_count", n=len(self._current_preset.champions)))
        else:
            self.lblChampCount.setText(tr("champ_count", n=0))

        # Правая панель
        if self._current_preset:
            self.lblTableTitle.setText(
                f"{self._current_preset.name}  [{team_type_display(self._current_preset.team_type)}]")
            self.lblPresetType.setText(f"🏆 {team_type_display(self._current_preset.team_type)}")
        else:
            self.lblTableTitle.setText(tr("select_preset"))
        self.btnAddChampion.setText(tr("btn_add_champion"))

        self.statusBar().showMessage(tr("status_ready"))

        # Обновляем список пресетов (там есть переведённый team_type в тексте — нет,
        # но язык влияет на цвет/иконку только опосредованно; сам список не хранит
        # переведённый текст, поэтому достаточно перерисовать)
        self._refresh_preset_list()

    def _on_language_changed(self):
        lang_code = self.comboLanguage.currentData()
        if lang_code:
            lang_manager.set_language(lang_code)

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
        current_row = self.listPresets.currentRow()
        self.listPresets.blockSignals(True)
        self.listPresets.clear()
        for preset in self._presets:
            item = QListWidgetItem(preset.name)
            color = "#C8AA6E" if preset.team_type == "Наша команда" else "#E74C3C"
            item.setForeground(QColor(color))
            # Иконка команды
            icon_text = "🔵" if preset.team_type == "Наша команда" else "🔴"
            item.setText(f"{icon_text} {preset.name}")
            self.listPresets.addItem(item)
        self.listPresets.blockSignals(False)
        if 0 <= current_row < self.listPresets.count():
            self.listPresets.setCurrentRow(current_row)

    def _on_preset_selected(self, row: int):
        if row < 0 or row >= len(self._presets):
            return
        self._current_preset = self._presets[row]
        self.champTable.set_champions(self._current_preset.champions)
        self.lblTableTitle.setText(
            f"{self._current_preset.name}  [{team_type_display(self._current_preset.team_type)}]")
        self.lblPresetName.setText(f"📋 {self._current_preset.name}")
        self.lblPresetType.setText(f"🏆 {team_type_display(self._current_preset.team_type)}")
        self.lblChampCount.setText(
            tr("champ_count", n=len(self._current_preset.champions)))
        self.statusBar().showMessage(
            tr("status_preset_info", name=self._current_preset.name,
               n=len(self._current_preset.champions)))

    def _new_preset(self):
        name, ok = QInputDialog.getText(self, tr("menu_new_preset"), tr("label_name"))
        if not ok or not name.strip():
            return

        team_options = [tr("team_ours"), tr("team_enemy")]
        internal_values = ["Наша команда", "Противники"]
        prompt = "Team type:" if lang_manager.get_language() == "en" else "Тип команды:"
        team_label, ok2 = QInputDialog.getItem(
            self, tr("menu_new_preset"), prompt,
            team_options, 0, False)
        if not ok2:
            return
        team_internal = internal_values[team_options.index(team_label)]

        preset = Preset(name=name.strip(), team_type=team_internal)
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)

    def _save_current_local(self):
        if not self._current_preset:
            QMessageBox.warning(self, tr("btn_save_json"), tr("select_preset"))
            return
        path = self._current_preset.save_local(PRESETS_DIR)
        self.statusBar().showMessage(path)
        QMessageBox.information(self, tr("btn_save_json"), path)

    def _load_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu_load_local"), PRESETS_DIR, "JSON (*.json)")
        if not path:
            return
        try:
            preset = Preset.load_local(path)
        except Exception as e:
            QMessageBox.critical(self, tr("menu_load_local"), str(e))
            return
        # Проверяем, не загружен ли уже
        for i, p in enumerate(self._presets):
            if p.name == preset.name:
                self._presets[i] = preset
                self._refresh_preset_list()
                self.listPresets.setCurrentRow(i)
                return
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)

    def _delete_current_preset(self):
        if not self._current_preset:
            return
        reply = QMessageBox.question(
            self, tr("btn_delete_preset"),
            f"{self._current_preset.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._presets.remove(self._current_preset)
            self._current_preset = None
            self._refresh_preset_list()
            self.champTable.set_champions([])
            self.lblTableTitle.setText(tr("select_preset"))

    # ── Google Sheets ──────────────────────────────────────────────────────────

    def _try_auto_connect_google(self):
        """Если service_account.json и ID таблицы уже настроены (например,
        капитан прислал готовую конфигурацию), пробуем подключиться сразу
        при запуске — без нажатия каких-либо кнопок пользователем."""
        if not sheets_manager.has_service_account_file():
            return
        if not sheets_manager.get_spreadsheet_id():
            return

        self._autoconnect_worker = _AutoConnectWorker(sheets_manager)
        self._autoconnect_worker.done.connect(self._on_auto_connect_done)
        self._autoconnect_worker.start()

    def _on_auto_connect_done(self, ok: bool, msg: str):
        self._update_google_status()
        self.statusBar().showMessage(f"☁ {msg}")

    def _open_google_dialog(self):
        dlg = GoogleSheetsDialog(self)
        dlg.presetLoaded.connect(self._load_from_google)
        dlg.exec()
        self._update_google_status()

    def _update_google_status(self):
        if sheets_manager.is_connected():
            self.lblGoogleStatus.setText(f"☁ {tr('gsheets_connected')}")
            self.lblGoogleStatus.setStyleSheet("color: #2ECC71; font-size: 11px;")
        else:
            self.lblGoogleStatus.setText(f"☁ {tr('gsheets_not_connected')}")
            self.lblGoogleStatus.setStyleSheet("color: #6A7A8A; font-size: 11px;")

    def _save_current_google(self):
        if not self._current_preset:
            QMessageBox.warning(self, tr("btn_save_sheets"), tr("select_preset"))
            return
        if not sheets_manager.is_connected():
            self._open_google_dialog()
            return
        ok, msg = sheets_manager.save_preset(self._current_preset)
        if ok:
            QMessageBox.information(self, tr("btn_save_sheets"), msg)
        else:
            QMessageBox.critical(self, tr("btn_save_sheets"), msg)
        self.statusBar().showMessage(msg)

    def _load_from_google(self, preset_name: str):
        if not sheets_manager.is_connected():
            return
        preset, msg = sheets_manager.load_preset(preset_name)
        if preset is None:
            QMessageBox.critical(self, tr("btn_load_preset"), msg)
            return
        # Обновляем или добавляем
        for i, p in enumerate(self._presets):
            if p.name == preset.name:
                self._presets[i] = preset
                self._refresh_preset_list()
                self.listPresets.setCurrentRow(i)
                return
        self._presets.append(preset)
        self._refresh_preset_list()
        self.listPresets.setCurrentRow(len(self._presets) - 1)

    # ── Чемпионы ──────────────────────────────────────────────────────────────

    def _add_champion(self):
        if not self._current_preset:
            QMessageBox.warning(self, tr("menu_add_champion"), tr("select_preset"))
            return
        dlg = ChampionDialog(parent=self)
        if dlg.exec():
            champ = dlg.get_champion()
            self._current_preset.champions.append(champ)
            self.champTable.set_champions(self._current_preset.champions)
            self.lblChampCount.setText(
                tr("champ_count", n=len(self._current_preset.champions)))

    def _edit_champion(self, idx: int):
        if not self._current_preset:
            return
        champ = self._current_preset.champions[idx]
        dlg = ChampionDialog(champ, parent=self)
        if dlg.exec():
            updated = dlg.get_champion()
            self._current_preset.champions[idx] = updated
            self.champTable.set_champions(self._current_preset.champions)

    def _delete_champion(self, idx: int):
        if not self._current_preset:
            return
        champ = self._current_preset.champions[idx]
        reply = QMessageBox.question(
            self, tr("btn_delete"),
            f"{champ.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._current_preset.champions.pop(idx)
            self.champTable.set_champions(self._current_preset.champions)
            self.lblChampCount.setText(
                tr("champ_count", n=len(self._current_preset.champions)))

    # ── Справка ───────────────────────────────────────────────────────────────

    def _show_about(self):
        lang = lang_manager.get_language()
        if lang == "en":
            text = (
                "<b>LoL Picks Manager</b><br>"
                "A tool for managing League of Legends tournament picks/bans<br><br>"
                "Features:<br>"
                "• Manage champion presets for different teams<br>"
                "• Role (Top/Jungle/Mid/ADC/Support) and damage class (AD/AP/Tank/Utility/Hybrid)<br>"
                "• Filter by role, damage class, tier and name<br>"
                "• Sort by role → damage class → tier<br>"
                "• Save to JSON (local) and Google Sheets (cloud, shared access)<br>"
                "• Champion and item icons<br>"
                "• Core and situational builds<br><br>"
                "Champion icons: <code>icons/champions/NAME.png</code><br>"
                "Item icons: <code>icons/items/NAME.png</code><br><br>"
                "Cloud sync uses a Google service account "
                "(<code>service_account.json</code>) — no browser login required."
            )
        else:
            text = (
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
        QMessageBox.about(self, tr("menu_about"), text)

    def closeEvent(self, event):
        # Автосохранение всех пресетов
        for preset in self._presets:
            try:
                preset.save_local(PRESETS_DIR)
            except Exception:
                pass
        event.accept()
