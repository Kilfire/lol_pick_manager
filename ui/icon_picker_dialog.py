"""
Диалог выбора иконки из встроенной галереи (icons/champions или icons/items).
Показывает сетку превью с возможностью поиска по имени файла.
Поддерживает переключение языка интерфейса (RU/EN).
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap

from core.i18n import tr, lang_manager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class _IconTile(QPushButton):
    """Одна плитка иконки в сетке — кликабельная превьюшка с подписью."""

    def __init__(self, filename: str, full_path: str, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.full_path = full_path

        self.setCheckable(True)
        self.setFixedSize(86, 100)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1E2A3A;
                border: 1px solid #2A3A4A;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #C89B3C;
                background-color: #243345;
            }
            QPushButton:checked {
                border: 2px solid #C89B3C;
                background-color: #2A3A4A;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        iconLabel = QLabel()
        iconLabel.setFixedSize(56, 56)
        iconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(full_path).scaled(
            54, 54, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        iconLabel.setPixmap(pix)
        layout.addWidget(iconLabel, alignment=Qt.AlignmentFlag.AlignHCenter)

        name = os.path.splitext(filename)[0]
        nameLabel = QLabel(name)
        nameLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nameLabel.setWordWrap(True)
        nameLabel.setStyleSheet("color: #B8C0CC; font-size: 9px; border: none;")
        layout.addWidget(nameLabel)


class IconPickerDialog(QDialog):
    """
    Окно выбора иконки внутри программы: показывает сетку всех изображений
    из заданной папки (по умолчанию icons/champions). Двойной клик или кнопка
    «Выбрать» возвращают относительный путь к файлу.

    Параметр title передаётся снаружи уже переведённым (вызывающий код сам
    решает, "Выбор иконки чемпиона" это или "Choose item icon").
    """

    def __init__(self, folder: str = "icons/champions", title: str = None, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.full_folder = os.path.join(BASE_DIR, folder)
        self._external_title = title
        self.setMinimumSize(640, 560)
        self.setModal(True)

        self._selected_path = None    # относительный путь icons/champions/Aatrox.png
        self._selected_name = None    # "Aatrox"
        self._tiles: list[_IconTile] = []

        self._build_ui()
        self._load_icons()
        self.retranslate_ui()

        lang_manager.add_listener(self.retranslate_ui)

    def closeEvent(self, event):
        lang_manager.remove_listener(self.retranslate_ui)
        super().closeEvent(event)

    def done(self, result):
        lang_manager.remove_listener(self.retranslate_ui)
        super().done(result)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Поиск ────────────────────────────────────────────────────────────
        searchRow = QHBoxLayout()
        self.lblSearch = QLabel()
        searchRow.addWidget(self.lblSearch)
        self.searchEdit = QLineEdit()
        self.searchEdit.textChanged.connect(self._apply_search)
        searchRow.addWidget(self.searchEdit, 1)
        layout.addLayout(searchRow)

        # ── Сетка иконок (прокручиваемая) ───────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #1E2A3A; border-radius: 4px; }")

        self.gridContainer = QWidget()
        self.gridLayout = QGridLayout(self.gridContainer)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.gridContainer)

        layout.addWidget(self.scroll, 1)

        # ── Статус ───────────────────────────────────────────────────────────
        self.lblStatus = QLabel("")
        self.lblStatus.setStyleSheet("color: #6A7A8A; font-size: 11px;")
        layout.addWidget(self.lblStatus)

        # ── Кнопки ───────────────────────────────────────────────────────────
        btnRow = QHBoxLayout()

        self.btnBrowse = QPushButton()
        self.btnBrowse.clicked.connect(self._browse_external)
        btnRow.addWidget(self.btnBrowse)

        btnRow.addStretch()

        self.btnCancel = QPushButton()
        self.btnCancel.clicked.connect(self.reject)
        btnRow.addWidget(self.btnCancel)

        self.btnSelect = QPushButton()
        self.btnSelect.setObjectName("btnSuccess")
        self.btnSelect.setEnabled(False)
        self.btnSelect.clicked.connect(self.accept)
        btnRow.addWidget(self.btnSelect)

        layout.addLayout(btnRow)

    # ── Перевод ───────────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self.setWindowTitle(self._external_title or tr("icon_picker_title_champ"))
        self.lblSearch.setText(tr("filter_search"))
        self.searchEdit.setPlaceholderText(tr("icon_search_ph"))
        self.btnBrowse.setText(tr("btn_browse_external"))
        self.btnCancel.setText(tr("btn_cancel"))
        self.btnSelect.setText(tr("btn_select"))
        self._update_status_text()

    def _update_status_text(self):
        if not self._all_files:
            self.lblStatus.setText(tr("no_icons_in_folder", folder=self.folder))
        else:
            shown = len(self._tiles)
            self.lblStatus.setText(tr("icons_found", n=shown))

    # ── Загрузка иконок ──────────────────────────────────────────────────────

    def _load_icons(self):
        self._all_files = []
        if os.path.isdir(self.full_folder):
            for fn in sorted(os.listdir(self.full_folder)):
                if fn.lower().endswith(IMAGE_EXTENSIONS):
                    self._all_files.append(fn)

        self._render_grid(self._all_files)

    def _render_grid(self, files: list[str]):
        # Очищаем текущую сетку
        while self.gridLayout.count():
            item = self.gridLayout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._tiles.clear()

        columns = 6
        for i, fn in enumerate(files):
            full_path = os.path.join(self.full_folder, fn)
            tile = _IconTile(fn, full_path)
            tile.clicked.connect(lambda checked, t=tile: self._on_tile_clicked(t))
            self.gridLayout.addWidget(tile, i // columns, i % columns)
            self._tiles.append(tile)

        self._update_status_text()

    def _apply_search(self, text: str):
        text = text.strip().lower()
        if not text:
            filtered = self._all_files
        else:
            filtered = [f for f in self._all_files if text in f.lower()]
        self._render_grid(filtered)

    # ── Выбор ─────────────────────────────────────────────────────────────────

    def _on_tile_clicked(self, tile: _IconTile):
        # Снимаем выделение со всех остальных плиток (одиночный выбор)
        for t in self._tiles:
            if t is not tile:
                t.setChecked(False)
        tile.setChecked(True)

        rel_path = os.path.relpath(tile.full_path, BASE_DIR)
        name_without_ext = os.path.splitext(tile.filename)[0]

        self._selected_path = rel_path
        self._selected_name = name_without_ext
        self.btnSelect.setEnabled(True)

    def _browse_external(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("btn_browse_external"), self.full_folder,
            "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self._selected_path = os.path.relpath(path, BASE_DIR)
            self._selected_name = os.path.splitext(os.path.basename(path))[0]
            self.accept()

    # ── Результат ────────────────────────────────────────────────────────────

    def get_selected(self) -> tuple[str, str]:
        """Возвращает (относительный_путь_к_иконке, имя_без_расширения)."""
        return self._selected_path or "", self._selected_name or ""
