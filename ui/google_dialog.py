"""
Диалог подключения к Google Sheets (через сервисный аккаунт) и управления
пресетами в облаке. Поддерживает переключение языка интерфейса (RU/EN).
"""
import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QTextEdit,
    QGroupBox, QFrame, QLineEdit, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.google_sheets import sheets_manager, SERVICE_ACCOUNT_FILE
from core.i18n import tr, lang_manager


class WorkerThread(QThread):
    """Выполняет блокирующий вызов (например, подключение к Google) в отдельном
    потоке, чтобы интерфейс программы не зависал во время ожидания ответа."""
    done = pyqtSignal(bool, str)

    def __init__(self, fn, *args):
        super().__init__()
        self._fn = fn
        self._args = args

    def run(self):
        result = self._fn(*self._args)
        if isinstance(result, tuple):
            self.done.emit(result[0], result[1])
        else:
            self.done.emit(True, str(result))


class GoogleSheetsDialog(QDialog):
    """Диалог управления Google Sheets."""

    presetLoaded = pyqtSignal(str)   # emit preset_name to load

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 600)
        self.setModal(True)
        self._build_ui()
        self.retranslate_ui()
        self._refresh_status()

        lang_manager.add_listener(self.retranslate_ui)

    def closeEvent(self, event):
        lang_manager.remove_listener(self.retranslate_ui)
        super().closeEvent(event)

    def done(self, result):
        lang_manager.remove_listener(self.retranslate_ui)
        super().done(result)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Настройка подключения ────────────────────────────────────────────
        self.grpSetup = QGroupBox()
        setupLayout = QVBoxLayout(self.grpSetup)

        self.lblCredStatus = QLabel()
        setupLayout.addWidget(self.lblCredStatus)

        self.lblBotEmail = QLabel()
        self.lblBotEmail.setWordWrap(True)
        self.lblBotEmail.setStyleSheet("color: #8A9AB0; font-size: 11px;")
        setupLayout.addWidget(self.lblBotEmail)

        row1 = QHBoxLayout()
        self.btnPickCreds = QPushButton()
        self.btnPickCreds.clicked.connect(self._pick_service_account)
        row1.addWidget(self.btnPickCreds)

        self.btnHowTo = QPushButton()
        self.btnHowTo.clicked.connect(self._open_howto)
        row1.addWidget(self.btnHowTo)
        setupLayout.addLayout(row1)

        idRow = QHBoxLayout()
        self.lblSpreadsheetId = QLabel()
        idRow.addWidget(self.lblSpreadsheetId)
        self.editSpreadsheetId = QLineEdit()
        idRow.addWidget(self.editSpreadsheetId, 1)
        setupLayout.addLayout(idRow)

        self.btnSaveId = QPushButton()
        self.btnSaveId.clicked.connect(self._save_spreadsheet_id)
        setupLayout.addWidget(self.btnSaveId)

        layout.addWidget(self.grpSetup)

        # ── Статус подключения ────────────────────────────────────────────────
        self.grpConn = QGroupBox()
        connLayout = QVBoxLayout(self.grpConn)

        self.lblStatus = QLabel()
        self.lblStatus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        connLayout.addWidget(self.lblStatus)

        row2 = QHBoxLayout()
        self.btnConnect = QPushButton()
        self.btnConnect.setObjectName("btnGoogle")
        self.btnConnect.clicked.connect(self._connect)
        row2.addWidget(self.btnConnect)

        self.btnDisconnect = QPushButton()
        self.btnDisconnect.clicked.connect(self._disconnect)
        row2.addWidget(self.btnDisconnect)

        self.btnOpenSheet = QPushButton()
        self.btnOpenSheet.clicked.connect(self._open_spreadsheet)
        row2.addWidget(self.btnOpenSheet)
        connLayout.addLayout(row2)

        layout.addWidget(self.grpConn)

        # ── Список пресетов в облаке ─────────────────────────────────────────
        self.grpPresets = QGroupBox()
        presLayout = QVBoxLayout(self.grpPresets)

        self.listPresets = QListWidget()
        presLayout.addWidget(self.listPresets)

        self.btnRefresh = QPushButton()
        self.btnRefresh.clicked.connect(self._refresh_presets)
        presLayout.addWidget(self.btnRefresh)

        presRow = QHBoxLayout()
        self.btnLoad = QPushButton()
        self.btnLoad.setObjectName("btnSuccess")
        self.btnLoad.clicked.connect(self._load_selected)
        presRow.addWidget(self.btnLoad)

        self.btnDelete = QPushButton()
        self.btnDelete.setObjectName("btnDanger")
        self.btnDelete.clicked.connect(self._delete_selected)
        presRow.addWidget(self.btnDelete)
        presLayout.addLayout(presRow)

        layout.addWidget(self.grpPresets)

        # ── Лог ──────────────────────────────────────────────────────────────
        self.grpLog = QGroupBox()
        logLayout = QVBoxLayout(self.grpLog)
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.setMaximumHeight(90)
        logLayout.addWidget(self.logEdit)
        layout.addWidget(self.grpLog)

        # ── Закрыть ───────────────────────────────────────────────────────────
        self.btnClose = QPushButton()
        self.btnClose.clicked.connect(self.accept)
        layout.addWidget(self.btnClose)

    # ── Перевод ───────────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self.setWindowTitle(tr("gsheets_title"))
        self.grpSetup.setTitle(tr("gsheets_setup_group"))
        self.btnPickCreds.setText(tr("btn_pick_credentials"))
        self.btnHowTo.setText(tr("btn_howto"))
        self.lblSpreadsheetId.setText(tr("label_spreadsheet_id"))
        self.btnSaveId.setText(tr("btn_save_spreadsheet_id"))

        self.grpConn.setTitle(tr("gsheets_conn_group"))
        self.btnConnect.setText(tr("btn_connect"))
        self.btnDisconnect.setText(tr("btn_disconnect"))
        self.btnOpenSheet.setText(tr("btn_open_sheet"))

        self.grpPresets.setTitle(tr("gsheets_presets_group"))
        self.btnRefresh.setText(tr("btn_refresh_list"))
        self.btnLoad.setText(tr("btn_load_preset"))
        self.btnDelete.setText(tr("btn_delete_preset_cloud"))

        self.grpLog.setTitle(tr("gsheets_log_group"))
        self.btnClose.setText(tr("btn_close"))

        self._refresh_status()

    # ── Вспомогательные ───────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.logEdit.append(msg)

    def _refresh_status(self):
        connected = sheets_manager.is_connected()
        if connected:
            self.lblStatus.setText(tr("gsheets_connected"))
            self.lblStatus.setStyleSheet("color: #2ECC71; font-weight: bold;")
        else:
            self.lblStatus.setText(tr("gsheets_disconnected_status"))
            self.lblStatus.setStyleSheet("color: #E74C3C;")

        self.btnConnect.setEnabled(not connected)
        self.btnDisconnect.setEnabled(connected)
        self.btnOpenSheet.setEnabled(connected or bool(sheets_manager.get_spreadsheet_id()))

        # Статус service_account.json
        if sheets_manager.has_service_account_file():
            self.lblCredStatus.setText(tr("gsheets_cred_found"))
            self.lblCredStatus.setStyleSheet("color: #2ECC71;")
            email = sheets_manager.get_service_account_email()
            self.lblBotEmail.setText(f"{tr('gsheets_bot_email')}\n{email}")
        else:
            self.lblCredStatus.setText(tr("gsheets_cred_not_found"))
            self.lblCredStatus.setStyleSheet("color: #E74C3C;")
            self.lblBotEmail.setText(tr("gsheets_bot_email"))

        self.editSpreadsheetId.setText(sheets_manager.get_spreadsheet_id())

        if connected:
            self._refresh_presets()

    def _pick_service_account(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("btn_pick_credentials"), ".",
            "JSON (*.json)")
        if path:
            import shutil
            shutil.copy(path, SERVICE_ACCOUNT_FILE)
            self._log(f"service_account.json ← {path}")
            self._refresh_status()

    def _save_spreadsheet_id(self):
        raw = self.editSpreadsheetId.text().strip()
        # Позволяем вставить как полную ссылку, так и голый ID
        if "docs.google.com" in raw and "/d/" in raw:
            try:
                raw = raw.split("/d/")[1].split("/")[0]
            except Exception:
                pass
        sheets_manager.set_spreadsheet_id(raw)
        self.editSpreadsheetId.setText(raw)
        self._log(f"ID: {raw}")

    def _connect(self):
        self._save_spreadsheet_id()
        self.btnConnect.setEnabled(False)
        self._log(tr("gsheets_disconnected_status"))   # placeholder cleared below

        self._worker = WorkerThread(sheets_manager.connect)
        self._worker.done.connect(self._on_connect_done)
        self._worker.start()

    def _on_connect_done(self, ok: bool, msg: str):
        self._log(msg)
        self._refresh_status()
        if not ok:
            self.btnConnect.setEnabled(True)
            QMessageBox.warning(self, tr("btn_connect"), msg)

    def _disconnect(self):
        sheets_manager.disconnect()
        self._refresh_status()

    def _open_spreadsheet(self):
        url = sheets_manager.get_spreadsheet_url()
        if url:
            webbrowser.open(url)

    def _open_howto(self):
        lang = lang_manager.get_language()
        if lang == "en":
            msg = """How to set up a shared spreadsheet for the team (one-time, done by the captain):

1. console.cloud.google.com → create a project
2. Enable "Google Sheets API" and "Google Drive API"
3. IAM & Admin → Service Accounts → Create
4. Open the account → "Keys" → Add key → JSON → download
5. Rename to service_account.json, place next to main.py
6. Create a Google Sheet → "Share" → paste the service account
   email (shown in this window after picking the file) → role "Editor"
7. Copy the spreadsheet ID from the browser address bar and paste
   it into the "Spreadsheet ID" field above → "Save spreadsheet ID"

After that, EVERY team member who has service_account.json and
knows the spreadsheet ID connects instantly — no browser, no
Google password needed."""
        else:
            msg = """Как настроить общую таблицу для команды (один раз, делает капитан):

1. console.cloud.google.com → создать проект
2. Включить «Google Sheets API» и «Google Drive API»
3. IAM и администрирование → Сервисные аккаунты → Создать
4. Открыть аккаунт → «Ключи» → Добавить ключ → JSON → скачать
5. Переименовать в service_account.json, положить рядом с main.py
6. Создать Google-таблицу → «Поделиться» → вставить email сервисного
   аккаунта (виден в этом окне после выбора файла) → роль «Редактор»
7. Скопировать ID таблицы из адресной строки браузера и вставить
   в поле «ID таблицы» выше → «Сохранить ID таблицы»

После этого КАЖДЫЙ член команды, получив файл service_account.json
и зная ID таблицы, подключается мгновенно — без браузера и без
ввода пароля Google."""
        QMessageBox.information(self, tr("btn_howto"), msg)

    def _refresh_presets(self):
        self.listPresets.clear()
        names = sheets_manager.list_presets()
        for name in names:
            self.listPresets.addItem(name)

    def _load_selected(self):
        item = self.listPresets.currentItem()
        if not item:
            return
        name = item.text()
        self.presetLoaded.emit(name)

    def _delete_selected(self):
        item = self.listPresets.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self, self.btnDelete.text(),
            f"{name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = sheets_manager.delete_preset(name)
            self._log(msg)
            if ok:
                self._refresh_presets()
