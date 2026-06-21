"""
Диалог добавления / редактирования чемпиона.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit,
    QGroupBox, QListWidget, QListWidgetItem, QFileDialog,
    QSizePolicy, QFrame, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

from core.models import (
    Champion, BuildItem, ROLES, DAMAGE_CLASSES, DETAILED_DAMAGE_TYPES,
    TIER_LIST,
)
from ui.icon_picker_dialog import IconPickerDialog

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BuildItemWidget(QWidget):
    """Виджет одного предмета билда (имя + иконка + кнопка удаления)."""

    def __init__(self, item: BuildItem, parent=None):
        super().__init__(parent)
        self.item = item
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Иконка предмета
        self.iconLabel = QLabel()
        self.iconLabel.setFixedSize(28, 28)
        self._set_icon(item.icon_path)
        layout.addWidget(self.iconLabel)

        # Имя предмета
        self.nameEdit = QLineEdit(item.name)
        self.nameEdit.setPlaceholderText("Название предмета")
        self.nameEdit.textChanged.connect(lambda t: setattr(self.item, "name", t))
        layout.addWidget(self.nameEdit, 1)

        # Выбор иконки
        btnIcon = QPushButton("📁")
        btnIcon.setFixedWidth(30)
        btnIcon.setToolTip("Выбрать иконку предмета")
        btnIcon.clicked.connect(self._pick_icon)
        layout.addWidget(btnIcon)

        # Удалить
        btnDel = QPushButton("✕")
        btnDel.setFixedWidth(28)
        btnDel.setObjectName("btnDanger")
        btnDel.clicked.connect(self._remove)
        layout.addWidget(btnDel)

    def _set_icon(self, path: str):
        if not path:
            self.iconLabel.setText("🗡️")
            return
        full = os.path.join(BASE_DIR, path) if not os.path.isabs(path) else path
        if os.path.exists(full):
            pix = QPixmap(full).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            self.iconLabel.setPixmap(pix)
        else:
            self.iconLabel.setText("🗡️")

    def _pick_icon(self):
        dlg = IconPickerDialog(
            folder="icons/items",
            title="Выбор иконки предмета",
            parent=self,
        )
        if dlg.exec():
            rel_path, name_guess = dlg.get_selected()
            if not rel_path:
                return
            self.item.icon_path = rel_path
            self._set_icon(rel_path)
            # Если поле названия предмета ещё пустое — подставим имя файла
            if not self.nameEdit.text().strip() and name_guess:
                self.nameEdit.setText(name_guess)

    def _remove(self):
        parent_layout = self.parent().layout() if self.parent() else None
        if parent_layout:
            parent_layout.removeWidget(self)
        self.deleteLater()

    def get_item(self) -> BuildItem:
        return BuildItem(name=self.nameEdit.text(), icon_path=self.item.icon_path)


class BuildSection(QGroupBox):
    """Секция билда (основной / ситуативный)."""

    def __init__(self, title: str, items: list, parent=None):
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._widgets: list[BuildItemWidget] = []

        for item in items:
            self._add_widget(item)

        btnAdd = QPushButton("+ Добавить предмет")
        btnAdd.clicked.connect(self._add_empty)
        self._layout.addWidget(btnAdd)

    def _add_widget(self, item: BuildItem):
        w = BuildItemWidget(item, self)
        self._layout.insertWidget(self._layout.count() - 1, w)
        self._widgets.append(w)

    def _add_empty(self):
        self._add_widget(BuildItem(""))

    def get_items(self) -> list:
        result = []
        for i in range(self._layout.count() - 1):
            widget = self._layout.itemAt(i).widget()
            if isinstance(widget, BuildItemWidget):
                item = widget.get_item()
                if item.name:
                    result.append(item)
        return result


class ChampionDialog(QDialog):
    """Диалог добавления / редактирования одного чемпиона.

    Роль (позиция: Топ/Лес/Мид/Адк/Сап) и Класс урона (АД/АП/Танк/Утилити/
    Гибрид) — независимые поля, так как один и тот же класс урона может
    встречаться на любой позиции (например, АП-мид и АП-сап). Подробный
    тип урона зависит от выбранного класса урона.
    """

    def __init__(self, champion: Champion = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Чемпион" if champion is None else f"Редактирование: {champion.name}")
        self.setMinimumSize(540, 700)
        self.setModal(True)

        self.champion = champion or Champion(name="", role=ROLES[0], damage_class=DAMAGE_CLASSES[0])
        self._icon_path = self.champion.icon_path

        self._build_ui()
        self._load_champion()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Scroll area для содержимого
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # ── Иконка + базовые поля ────────────────────────────────────────────
        topRow = QHBoxLayout()

        self.iconLabel = QLabel()
        self.iconLabel.setFixedSize(72, 72)
        self.iconLabel.setStyleSheet(
            "border: 2px solid #C89B3C; border-radius: 4px; background: #1E2A3A;")
        self.iconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.iconLabel.setText("?")
        topRow.addWidget(self.iconLabel)

        btnPickIcon = QPushButton("🖼 Выбрать иконку")
        btnPickIcon.setToolTip("Открыть галерею иконок чемпионов")
        btnPickIcon.clicked.connect(self._pick_champion_icon)
        topRow.addWidget(btnPickIcon, alignment=Qt.AlignmentFlag.AlignTop)
        topRow.addStretch()
        layout.addLayout(topRow)

        # ── Форма ────────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)

        self.editName = QLineEdit()
        self.editName.setPlaceholderText("Введите имя чемпиона")
        form.addRow("Имя:", self.editName)

        self.comboRole = QComboBox()
        self.comboRole.addItems(ROLES)
        form.addRow("Роль (позиция):", self.comboRole)

        self.comboClass = QComboBox()
        self.comboClass.addItems(DAMAGE_CLASSES)
        self.comboClass.currentTextChanged.connect(self._update_detailed_types)
        form.addRow("Класс урона:", self.comboClass)

        self.comboDetailed = QComboBox()
        form.addRow("Подробный тип:", self.comboDetailed)

        self.comboTier = QComboBox()
        self.comboTier.addItems(TIER_LIST)
        form.addRow("Место в тирлисте:", self.comboTier)

        layout.addLayout(form)

        # ── Билд: основной ───────────────────────────────────────────────────
        self.buildCore = BuildSection(
            "🗡️ Основной билд", self.champion.build_core)
        layout.addWidget(self.buildCore)

        # ── Билд: ситуативный ────────────────────────────────────────────────
        self.buildSit = BuildSection(
            "⚡ Ситуативные предметы", self.champion.build_situational)
        layout.addWidget(self.buildSit)

        # ── Заметки ──────────────────────────────────────────────────────────
        grpNotes = QGroupBox("📝 Заметки")
        notesLayout = QVBoxLayout(grpNotes)
        self.editNotes = QTextEdit()
        self.editNotes.setPlaceholderText(
            "Сильные стороны, слабые стороны, советы по пику...")
        self.editNotes.setMaximumHeight(80)
        notesLayout.addWidget(self.editNotes)
        layout.addWidget(grpNotes)

        root.addWidget(scroll, 1)

        # ── Кнопки ───────────────────────────────────────────────────────────
        btnRow = QHBoxLayout()
        btnSave = QPushButton("✔ Сохранить")
        btnSave.setObjectName("btnSuccess")
        btnSave.clicked.connect(self._save)

        btnCancel = QPushButton("Отмена")
        btnCancel.clicked.connect(self.reject)

        btnRow.addStretch()
        btnRow.addWidget(btnCancel)
        btnRow.addWidget(btnSave)
        root.addLayout(btnRow)

        # Инициализируем подробные типы под первый класс урона
        self._update_detailed_types(DAMAGE_CLASSES[0])

    # ── Логика ───────────────────────────────────────────────────────────────

    def _load_champion(self):
        self.editName.setText(self.champion.name)

        idx_r = self.comboRole.findText(self.champion.role)
        if idx_r >= 0:
            self.comboRole.setCurrentIndex(idx_r)

        idx_c = self.comboClass.findText(self.champion.damage_class)
        if idx_c >= 0:
            self.comboClass.setCurrentIndex(idx_c)

        self._update_detailed_types(self.champion.damage_class)
        idx_d = self.comboDetailed.findText(self.champion.damage_type)
        if idx_d >= 0:
            self.comboDetailed.setCurrentIndex(idx_d)

        idx_t = self.comboTier.findText(self.champion.tier)
        if idx_t >= 0:
            self.comboTier.setCurrentIndex(idx_t)

        self.editNotes.setPlainText(self.champion.notes)
        self._refresh_icon()

    def _update_detailed_types(self, damage_class: str):
        self.comboDetailed.clear()
        self.comboDetailed.addItems(DETAILED_DAMAGE_TYPES.get(damage_class, []))

    def _pick_champion_icon(self):
        dlg = IconPickerDialog(
            folder="icons/champions",
            title="Выбор иконки чемпиона",
            parent=self,
        )
        if dlg.exec():
            rel_path, name_guess = dlg.get_selected()
            if not rel_path:
                return
            self._icon_path = rel_path
            self._refresh_icon()

            # Автозаполнение имени чемпиона по имени файла иконки.
            # Поле остаётся редактируемым — пользователь может тут же поправить.
            if name_guess:
                self.editName.setText(name_guess)
                self.editName.selectAll()
                self.editName.setFocus()

    def _refresh_icon(self):
        if not self._icon_path:
            self.iconLabel.setText("?")
            return
        full = os.path.join(BASE_DIR, self._icon_path) \
            if not os.path.isabs(self._icon_path) else self._icon_path
        if os.path.exists(full):
            pix = QPixmap(full).scaled(70, 70,
                                       Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            self.iconLabel.setPixmap(pix)
        else:
            self.iconLabel.setText("?")

    def _save(self):
        name = self.editName.text().strip()
        if not name:
            self.editName.setFocus()
            return

        self.champion.name         = name
        self.champion.role         = self.comboRole.currentText()
        self.champion.damage_class = self.comboClass.currentText()
        self.champion.damage_type  = self.comboDetailed.currentText()
        self.champion.tier         = self.comboTier.currentText()
        self.champion.icon_path    = self._icon_path
        self.champion.notes        = self.editNotes.toPlainText().strip()
        self.champion.build_core        = self.buildCore.get_items()
        self.champion.build_situational = self.buildSit.get_items()

        self.accept()

    def get_champion(self) -> Champion:
        return self.champion
