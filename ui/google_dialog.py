"""
Диалог подключения к Google Sheets (через сервисный аккаунт) и управления
пресетами в облаке.
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
        self.setWindowTitle("☁ Google Sheets")
        self.setMinimumSize(520, 600)
        self.setModal(True)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Настройка подключения ────────────────────────────────────────────
        grpSetup = QGroupBox("Настройка подключения")
        setupLayout = QVBoxLayout(grpSetup)

        self.lblCredStatus = QLabel("service_account.json: не найден")
        setupLayout.addWidget(self.lblCredStatus)

        self.lblBotEmail = QLabel("Email сервисного аккаунта: —")
        self.lblBotEmail.setWordWrap(True)
        self.lblBotEmail.setStyleSheet("color: #8A9AB0; font-size: 11px;")
        setupLayout.addWidget(self.lblBotEmail)

        row1 = QHBoxLayout()
        btnPickCreds = QPushButton("📁 Выбрать service_account.json")
        btnPickCreds.clicked.connect(self._pick_service_account)
        row1.addWidget(btnPickCreds)

        btnHowTo = QPushButton("? Как настроить?")
        btnHowTo.clicked.connect(self._open_howto)
        row1.addWidget(btnHowTo)
        setupLayout.addLayout(row1)

        idRow = QHBoxLayout()
        idRow.addWidget(QLabel("ID таблицы:"))
        self.editSpreadsheetId = QLineEdit()
        self.editSpreadsheetId.setPlaceholderText(
            "Например: 1kFGXyIg13DdVI-2GxYHtBMW0K5znEkezitexhpmWX0s")
        idRow.addWidget(self.editSpreadsheetId, 1)
        setupLayout.addLayout(idRow)

        btnSaveId = QPushButton("💾 Сохранить ID таблицы")
        btnSaveId.clicked.connect(self._save_spreadsheet_id)
        setupLayout.addWidget(btnSaveId)

        layout.addWidget(grpSetup)

        # ── Статус подключения ────────────────────────────────────────────────
        grpConn = QGroupBox("Подключение")
        connLayout = QVBoxLayout(grpConn)

        self.lblStatus = QLabel("Не подключено")
        self.lblStatus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        connLayout.addWidget(self.lblStatus)

        row2 = QHBoxLayout()
        self.btnConnect = QPushButton("🔗 Подключиться")
        self.btnConnect.setObjectName("btnGoogle")
        self.btnConnect.clicked.connect(self._connect)
        row2.addWidget(self.btnConnect)

        self.btnDisconnect = QPushButton("Отключиться")
        self.btnDisconnect.clicked.connect(self._disconnect)
        row2.addWidget(self.btnDisconnect)

        self.btnOpenSheet = QPushButton("🌐 Открыть таблицу")
        self.btnOpenSheet.clicked.connect(self._open_spreadsheet)
        row2.addWidget(self.btnOpenSheet)
        connLayout.addLayout(row2)

        layout.addWidget(grpConn)

        # ── Список пресетов в облаке ─────────────────────────────────────────
        grpPresets = QGroupBox("☁ Пресеты в Google Sheets")
        presLayout = QVBoxLayout(grpPresets)

        self.listPresets = QListWidget()
        presLayout.addWidget(self.listPresets)

        btnRefresh = QPushButton("🔄 Обновить список")
        btnRefresh.clicked.connect(self._refresh_presets)
        presLayout.addWidget(btnRefresh)

        presRow = QHBoxLayout()
        btnLoad = QPushButton("⬇ Загрузить пресет")
        btnLoad.setObjectName("btnSuccess")
        btnLoad.clicked.connect(self._load_selected)
        presRow.addWidget(btnLoad)

        btnDelete = QPushButton("✕ Удалить пресет")
        btnDelete.setObjectName("btnDanger")
        btnDelete.clicked.connect(self._delete_selected)
        presRow.addWidget(btnDelete)
        presLayout.addLayout(presRow)

        layout.addWidget(grpPresets)

        # ── Лог ──────────────────────────────────────────────────────────────
        grpLog = QGroupBox("Журнал")
        logLayout = QVBoxLayout(grpLog)
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.setMaximumHeight(90)
        logLayout.addWidget(self.logEdit)
        layout.addWidget(grpLog)

        # ── Закрыть ───────────────────────────────────────────────────────────
        btnClose = QPushButton("Закрыть")
        btnClose.clicked.connect(self.accept)
        layout.addWidget(btnClose)

    # ── Вспомогательные ───────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.logEdit.append(msg)

    def _refresh_status(self):
        connected = sheets_manager.is_connected()
        if connected:
            self.lblStatus.setText("✅ Подключено к Google Sheets")
            self.lblStatus.setStyleSheet("color: #2ECC71; font-weight: bold;")
        else:
            self.lblStatus.setText("❌ Не подключено")
            self.lblStatus.setStyleSheet("color: #E74C3C;")

        self.btnConnect.setEnabled(not connected)
        self.btnDisconnect.setEnabled(connected)
        self.btnOpenSheet.setEnabled(connected or bool(sheets_manager.get_spreadsheet_id()))

        # Статус service_account.json
        if sheets_manager.has_service_account_file():
            self.lblCredStatus.setText("service_account.json: ✅ найден")
            self.lblCredStatus.setStyleSheet("color: #2ECC71;")
            email = sheets_manager.get_service_account_email()
            self.lblBotEmail.setText(
                f"Email сервисного аккаунта (дайте ему доступ «Редактор» к таблице):\n{email}")
        else:
            self.lblCredStatus.setText("service_account.json: ❌ не найден")
            self.lblCredStatus.setStyleSheet("color: #E74C3C;")
            self.lblBotEmail.setText("Email сервисного аккаунта: —")

        self.editSpreadsheetId.setText(sheets_manager.get_spreadsheet_id())

        if connected:
            self._refresh_presets()

    def _pick_service_account(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать service_account.json", ".",
            "JSON (*.json)")
        if path:
            import shutil
            shutil.copy(path, SERVICE_ACCOUNT_FILE)
            self._log(f"service_account.json скопирован из {path}")
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
        self._log(f"ID таблицы сохранён: {raw}")

    def _connect(self):
        self._save_spreadsheet_id()
        self.btnConnect.setEnabled(False)
        self.btnConnect.setText("Подключение...")
        self._log("Выполняется подключение к Google Sheets...")

        self._worker = WorkerThread(sheets_manager.connect)
        self._worker.done.connect(self._on_connect_done)
        self._worker.start()

    def _on_connect_done(self, ok: bool, msg: str):
        self._log(msg)
        self._refresh_status()
        if not ok:
            self.btnConnect.setText("🔗 Подключиться")
            self.btnConnect.setEnabled(True)
            QMessageBox.warning(self, "Не удалось подключиться", msg)
        else:
            self.btnConnect.setText("🔗 Подключиться")

    def _disconnect(self):
        sheets_manager.disconnect()
        self._log("Отключено от Google Sheets")
        self._refresh_status()

    def _open_spreadsheet(self):
        url = sheets_manager.get_spreadsheet_url()
        if url:
            webbrowser.open(url)

    def _open_howto(self):
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
        QMessageBox.information(self, "Как настроить подключение", msg)

    def _refresh_presets(self):
        self.listPresets.clear()
        names = sheets_manager.list_presets()
        for name in names:
            self.listPresets.addItem(name)
        if not names and sheets_manager.is_connected():
            self._log("В таблице пока нет пресетов")

    def _load_selected(self):
        item = self.listPresets.currentItem()
        if not item:
            return
        name = item.text()
        self.presetLoaded.emit(name)
        self._log(f"Запрошена загрузка пресета «{name}»")

    def _delete_selected(self):
        item = self.listPresets.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self, "Удалить пресет",
            f"Удалить пресет «{name}» из Google Sheets?\nДействие необратимо.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = sheets_manager.delete_preset(name)
            self._log(msg)
            if ok:
                self._refresh_presets()
