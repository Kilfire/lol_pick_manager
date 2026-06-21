"""
Диалог добавления / редактирования чемпиона.
Поддерживает переключение языка интерфейса (RU/EN).
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
    TIER_LIST, role_display, damage_class_display,
)
from core.i18n import tr, lang_manager
from ui.icon_picker_dialog import IconPickerDialog

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _set_combo_items(combo: QComboBox, items: list[str], display_fn=None):
    """Заполняет ComboBox парами (переведённый_текст, внутреннее_значение)."""
    combo.clear()
    for value in items:
        label = display_fn(value) if display_fn else value
        combo.addItem(label, value)


def _select_combo_by_data(combo: QComboBox, value: str):
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


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
        self.nameEdit.setPlaceholderText(tr("item_name_ph"))
        self.nameEdit.textChanged.connect(lambda t: setattr(self.item, "name", t))
        layout.addWidget(self.nameEdit, 1)

        # Выбор иконки
        self.btnIcon = QPushButton("📁")
        self.btnIcon.setFixedWidth(30)
        self.btnIcon.setToolTip(tr("btn_pick_icon"))
        self.btnIcon.clicked.connect(self._pick_icon)
        layout.addWidget(self.btnIcon)

        # Удалить
        btnDel = QPushButton("✕")
        btnDel.setFixedWidth(28)
        btnDel.setObjectName("btnDanger")
        btnDel.clicked.connect(self._remove)
        layout.addWidget(btnDel)

        lang_manager.add_listener(self.retranslate_ui)

    def retranslate_ui(self):
        self.nameEdit.setPlaceholderText(tr("item_name_ph"))
        self.btnIcon.setToolTip(tr("btn_pick_icon"))

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
            title=tr("icon_picker_title_item"),
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
        lang_manager.remove_listener(self.retranslate_ui)
        parent_layout = self.parent().layout() if self.parent() else None
        if parent_layout:
            parent_layout.removeWidget(self)
        self.deleteLater()

    def get_item(self) -> BuildItem:
        return BuildItem(name=self.nameEdit.text(), icon_path=self.item.icon_path)


class BuildSection(QGroupBox):
    """Секция билда (основной / ситуативный)."""

    def __init__(self, title_key: str, items: list, parent=None):
        super().__init__(tr(title_key), parent)
        self._title_key = title_key
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._widgets: list[BuildItemWidget] = []

        for item in items:
            self._add_widget(item)

        self.btnAdd = QPushButton(tr("btn_add_item"))
        self.btnAdd.clicked.connect(self._add_empty)
        self._layout.addWidget(self.btnAdd)

        lang_manager.add_listener(self.retranslate_ui)

    def retranslate_ui(self):
        self.setTitle(tr(self._title_key))
        self.btnAdd.setText(tr("btn_add_item"))

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

    ComboBox-ы ролей/класса хранят ВНУТРЕННЕЕ (русское) значение через
    userData — поэтому переключение языка не теряет выбор.
    """

    def __init__(self, champion: Champion = None, parent=None):
        super().__init__(parent)
        self._is_edit = champion is not None
        self._edit_name = champion.name if champion else ""
        self.setMinimumSize(540, 700)
        self.setModal(True)

        self.champion = champion or Champion(name="", role=ROLES[0], damage_class=DAMAGE_CLASSES[0])
        self._icon_path = self.champion.icon_path

        self._build_ui()
        self._load_champion()
        self._update_window_title()

        lang_manager.add_listener(self.retranslate_ui)

    def _update_window_title(self):
        if self._is_edit:
            self.setWindowTitle(tr("champion_dialog_edit_title", name=self._edit_name))
        else:
            self.setWindowTitle(tr("champion_dialog_title"))

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

        self.btnPickIcon = QPushButton()
        self.btnPickIcon.clicked.connect(self._pick_champion_icon)
        topRow.addWidget(self.btnPickIcon, alignment=Qt.AlignmentFlag.AlignTop)
        topRow.addStretch()
        layout.addLayout(topRow)

        # ── Форма ────────────────────────────────────────────────────────────
        self.form = QFormLayout()
        self.form.setSpacing(10)

        self.editName = QLineEdit()
        self.lblName = QLabel()
        self.form.addRow(self.lblName, self.editName)

        self.comboRole = QComboBox()
        _set_combo_items(self.comboRole, ROLES, role_display)
        self.lblRole = QLabel()
        self.form.addRow(self.lblRole, self.comboRole)

        self.comboClass = QComboBox()
        _set_combo_items(self.comboClass, DAMAGE_CLASSES, damage_class_display)
        self.comboClass.currentIndexChanged.connect(
            lambda _: self._update_detailed_types(self.comboClass.currentData()))
        self.lblClass = QLabel()
        self.form.addRow(self.lblClass, self.comboClass)

        self.comboDetailed = QComboBox()
        self.lblDetailed = QLabel()
        self.form.addRow(self.lblDetailed, self.comboDetailed)

        self.comboTier = QComboBox()
        self.comboTier.addItems(TIER_LIST)   # тиры (S/A/B/C) не переводятся
        self.lblTier = QLabel()
        self.form.addRow(self.lblTier, self.comboTier)

        layout.addLayout(self.form)

        # ── Билд: основной ───────────────────────────────────────────────────
        self.buildCore = BuildSection(
            "group_build_core", self.champion.build_core)
        layout.addWidget(self.buildCore)

        # ── Билд: ситуативный ────────────────────────────────────────────────
        self.buildSit = BuildSection(
            "group_build_sit", self.champion.build_situational)
        layout.addWidget(self.buildSit)

        # ── Заметки ──────────────────────────────────────────────────────────
        self.grpNotes = QGroupBox()
        notesLayout = QVBoxLayout(self.grpNotes)
        self.editNotes = QTextEdit()
        self.editNotes.setMaximumHeight(80)
        notesLayout.addWidget(self.editNotes)
        layout.addWidget(self.grpNotes)

        root.addWidget(scroll, 1)

        # ── Кнопки ───────────────────────────────────────────────────────────
        btnRow = QHBoxLayout()
        self.btnSave = QPushButton()
        self.btnSave.setObjectName("btnSuccess")
        self.btnSave.clicked.connect(self._save)

        self.btnCancel = QPushButton()
        self.btnCancel.clicked.connect(self.reject)

        btnRow.addStretch()
        btnRow.addWidget(self.btnCancel)
        btnRow.addWidget(self.btnSave)
        root.addLayout(btnRow)

        # Инициализируем подробные типы под первый класс урона
        self._update_detailed_types(DAMAGE_CLASSES[0])

        self.retranslate_ui()

    # ── Перевод ───────────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self._update_window_title()

        self.btnPickIcon.setText(tr("btn_pick_icon"))
        self.btnPickIcon.setToolTip(tr("icon_picker_title_champ"))

        self.lblName.setText(tr("label_name"))
        self.editName.setPlaceholderText(tr("name_placeholder"))

        self.lblRole.setText(tr("label_role"))
        self.lblClass.setText(tr("label_class"))
        self.lblDetailed.setText(tr("label_detailed"))
        self.lblTier.setText(tr("label_tier"))

        # Перестраиваем комбобоксы ролей/класса с сохранением выбора
        prev_role = self.comboRole.currentData()
        _set_combo_items(self.comboRole, ROLES, role_display)
        if prev_role:
            _select_combo_by_data(self.comboRole, prev_role)

        prev_class = self.comboClass.currentData()
        _set_combo_items(self.comboClass, DAMAGE_CLASSES, damage_class_display)
        if prev_class:
            _select_combo_by_data(self.comboClass, prev_class)
        self._update_detailed_types(self.comboClass.currentData())

        self.grpNotes.setTitle(tr("group_notes"))
        self.editNotes.setPlaceholderText(tr("notes_placeholder"))

        self.btnSave.setText(tr("btn_confirm_save"))
        self.btnCancel.setText(tr("btn_cancel"))

    # ── Логика ───────────────────────────────────────────────────────────────

    def _load_champion(self):
        self.editName.setText(self.champion.name)

        _select_combo_by_data(self.comboRole, self.champion.role)
        _select_combo_by_data(self.comboClass, self.champion.damage_class)

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
        if not damage_class:
            return
        self.comboDetailed.clear()
        # Подробные типы урона пока не переведены (используются как произвольный
        # описательный текст, специфичный для каждого класса урона)
        self.comboDetailed.addItems(DETAILED_DAMAGE_TYPES.get(damage_class, []))

    def _pick_champion_icon(self):
        dlg = IconPickerDialog(
            folder="icons/champions",
            title=tr("icon_picker_title_champ"),
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
        self.champion.role         = self.comboRole.currentData()
        self.champion.damage_class = self.comboClass.currentData()
        self.champion.damage_type  = self.comboDetailed.currentText()
        self.champion.tier         = self.comboTier.currentText()
        self.champion.icon_path    = self._icon_path
        self.champion.notes        = self.editNotes.toPlainText().strip()
        self.champion.build_core        = self.buildCore.get_items()
        self.champion.build_situational = self.buildSit.get_items()

        self.accept()

    def get_champion(self) -> Champion:
        return self.champion
