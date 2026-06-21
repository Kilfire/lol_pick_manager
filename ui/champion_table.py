"""
Таблица чемпионов с фильтрацией, иконками и инлайн-редактированием.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QComboBox, QLineEdit, QPushButton,
    QAbstractItemView, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QBrush, QFont

from core.models import Champion, ROLES, DAMAGE_CLASSES, DAMAGE_CLASS_COLORS, TIER_LIST

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COLUMNS = [
    ("icon",       "Иконка",           48),
    ("name",       "Имя",             140),
    ("role",       "Роль",             80),
    ("class",      "Класс урона",     110),
    ("detailed",   "Подробный тип",   120),
    ("build",      "Основной билд",   200),
    ("situational","Ситуативные",     180),
    ("tier",       "Тир",              55),
    ("notes",      "Заметки",         180),
]


class DamageClassChip(QLabel):
    """Чип класса урона: фон одинаковый тёмный/чёрный у всех, цвет текста и
    обводки отличается по классу (АД/АП/Танк/Утилити/Гибрид)."""

    def __init__(self, damage_class: str, parent=None):
        super().__init__(damage_class, parent)
        color = DAMAGE_CLASS_COLORS.get(damage_class, "#888")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #000000;
                border: 1px solid {color};
                border-radius: 10px;
                color: {color};
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class RoleChip(QLabel):
    """Нейтральный чип позиции (Топ/Лес/Мид/Адк/Сап) — одинаковый стиль для всех."""

    def __init__(self, role: str, parent=None):
        super().__init__(role, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 1px solid #C89B3C;
                border-radius: 10px;
                color: #C89B3C;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class TierBadge(QLabel):
    """Бейдж тира (S/A/B/C)."""

    TIER_COLORS = {
        "S": "#E74C3C",
        "A": "#E67E22",
        "B": "#3498DB",
        "C": "#95A5A6",
    }

    def __init__(self, tier: str, parent=None):
        super().__init__(tier, parent)
        color = self.TIER_COLORS.get(tier, "#888")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.setFont(font)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: #fff;
                border-radius: 14px;
                padding: 0 8px;
                min-width: 28px;
                min-height: 28px;
            }}
        """)


class ChampionTable(QWidget):
    """Таблица чемпионов с фильтрацией, сортировкой и действиями.

    Сортировка по умолчанию: роль (Топ→Лес→Мид→Адк→Сап), затем класс урона
    (АД→АП→Танк→Утилити→Гибрид), затем тир, затем имя.
    """

    editRequested   = pyqtSignal(int)   # индекс чемпиона в списке
    deleteRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._champions: list[Champion] = []
        self._filtered:  list[Champion] = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Строка фильтров ───────────────────────────────────────────────────
        filterRow = QHBoxLayout()

        filterRow.addWidget(QLabel("Роль:"))
        self.comboFilterRole = QComboBox()
        self.comboFilterRole.addItem("Все роли")
        self.comboFilterRole.addItems(ROLES)
        self.comboFilterRole.currentTextChanged.connect(self._apply_filter)
        filterRow.addWidget(self.comboFilterRole)

        filterRow.addWidget(QLabel("Класс урона:"))
        self.comboFilterClass = QComboBox()
        self.comboFilterClass.addItem("Все классы")
        self.comboFilterClass.addItems(DAMAGE_CLASSES)
        self.comboFilterClass.currentTextChanged.connect(self._apply_filter)
        filterRow.addWidget(self.comboFilterClass)

        filterRow.addWidget(QLabel("Тир:"))
        self.comboFilterTier = QComboBox()
        self.comboFilterTier.addItem("Все тиры")
        self.comboFilterTier.addItems(TIER_LIST)
        self.comboFilterTier.currentTextChanged.connect(self._apply_filter)
        filterRow.addWidget(self.comboFilterTier)

        filterRow.addWidget(QLabel("Поиск:"))
        self.searchEdit = QLineEdit()
        self.searchEdit.setPlaceholderText("Имя чемпиона...")
        self.searchEdit.textChanged.connect(self._apply_filter)
        filterRow.addWidget(self.searchEdit, 1)

        btnReset = QPushButton("✕ Сбросить")
        btnReset.clicked.connect(self._reset_filter)
        filterRow.addWidget(btnReset)

        layout.addLayout(filterRow)

        # ── Статистика ────────────────────────────────────────────────────────
        self.lblStats = QLabel("")
        self.lblStats.setStyleSheet("color: #6A7A8A; font-size: 11px;")
        layout.addWidget(self.lblStats)

        # ── Таблица ───────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.horizontalHeader().setStretchLastSection(True)

        for i, (_, _, w) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, w)

        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)   # Имя растягивается

        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        # ── Кнопки действий ───────────────────────────────────────────────────
        actionRow = QHBoxLayout()
        actionRow.addStretch()

        btnEdit = QPushButton("✏ Редактировать")
        btnEdit.clicked.connect(self._edit_selected)
        actionRow.addWidget(btnEdit)

        btnDel = QPushButton("🗑 Удалить")
        btnDel.setObjectName("btnDanger")
        btnDel.clicked.connect(self._delete_selected)
        actionRow.addWidget(btnDel)

        layout.addLayout(actionRow)

    # ── Данные ────────────────────────────────────────────────────────────────

    def set_champions(self, champions: list[Champion]):
        self._champions = champions
        self._apply_filter()

    def _apply_filter(self):
        role = self.comboFilterRole.currentText()
        dmg_class = self.comboFilterClass.currentText()
        tier = self.comboFilterTier.currentText()
        search = self.searchEdit.text().strip().lower()

        filtered = [
            c for c in self._champions
            if (role == "Все роли" or c.role == role)
            and (dmg_class == "Все классы" or c.damage_class == dmg_class)
            and (tier == "Все тиры" or c.tier == tier)
            and (not search or search in c.name.lower())
        ]

        # Сортировка: роль → класс урона → тир → имя
        self._filtered = sorted(filtered, key=lambda c: c.sort_key())

        self._render()

    def _reset_filter(self):
        self.comboFilterRole.setCurrentIndex(0)
        self.comboFilterClass.setCurrentIndex(0)
        self.comboFilterTier.setCurrentIndex(0)
        self.searchEdit.clear()

    def _render(self):
        self.table.setRowCount(0)

        for row_idx, champ in enumerate(self._filtered):
            self.table.insertRow(row_idx)
            self.table.setRowHeight(row_idx, 52)

            # 0 — Иконка
            iconLabel = self._make_icon_label(champ.icon_path, champ.name)
            self.table.setCellWidget(row_idx, 0, iconLabel)

            # 1 — Имя
            nameItem = QTableWidgetItem(champ.name)
            nameItem.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            nameItem.setData(Qt.ItemDataRole.UserRole, self._champions.index(champ))
            self.table.setItem(row_idx, 1, nameItem)

            # 2 — Роль (нейтральный чип)
            roleWrap = QWidget()
            roleLayout = QHBoxLayout(roleWrap)
            roleLayout.setContentsMargins(6, 0, 6, 0)
            roleLayout.addWidget(RoleChip(champ.role))
            roleLayout.addStretch()
            self.table.setCellWidget(row_idx, 2, roleWrap)

            # 3 — Класс урона (цветной чип, чёрный фон)
            classWrap = QWidget()
            classLayout = QHBoxLayout(classWrap)
            classLayout.setContentsMargins(6, 0, 6, 0)
            classLayout.addWidget(DamageClassChip(champ.damage_class))
            classLayout.addStretch()
            self.table.setCellWidget(row_idx, 3, classWrap)

            # 4 — Подробный тип урона
            dmgItem = QTableWidgetItem(champ.damage_type)
            dmgItem.setForeground(QBrush(QColor("#A0A8C0")))
            self.table.setItem(row_idx, 4, dmgItem)

            # 5 — Основной билд (иконки или текст)
            buildWidget = self._make_build_widget(champ.build_core)
            self.table.setCellWidget(row_idx, 5, buildWidget)

            # 6 — Ситуативные
            sitWidget = self._make_build_widget(champ.build_situational)
            self.table.setCellWidget(row_idx, 6, sitWidget)

            # 7 — Тир (бейдж)
            tierWrap = QWidget()
            tierLayout = QHBoxLayout(tierWrap)
            tierLayout.setContentsMargins(4, 0, 4, 0)
            tierLayout.addWidget(TierBadge(champ.tier))
            tierLayout.addStretch()
            self.table.setCellWidget(row_idx, 7, tierWrap)

            # 8 — Заметки
            notesItem = QTableWidgetItem(champ.notes)
            notesItem.setForeground(QBrush(QColor("#7A8A9A")))
            notesItem.setFont(QFont("Segoe UI", 10))
            self.table.setItem(row_idx, 8, notesItem)

        total = len(self._champions)
        shown = len(self._filtered)
        self.lblStats.setText(
            f"Показано: {shown} из {total} чемпионов  •  отсортировано по роли и классу урона")

    # ── Виджеты ячеек ─────────────────────────────────────────────────────────

    def _make_icon_label(self, icon_path: str, name: str) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(4, 4, 4, 4)
        label = QLabel()
        label.setFixedSize(44, 44)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon_path:
            full = os.path.join(BASE_DIR, icon_path) \
                if not os.path.isabs(icon_path) else icon_path
            if os.path.exists(full):
                pix = QPixmap(full).scaled(
                    44, 44,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(pix)
                label.setStyleSheet(
                    "border: 1px solid #C89B3C; border-radius: 3px;")
            else:
                label.setText(name[:2].upper() if name else "?")
                label.setStyleSheet(
                    "background:#1E2A3A; border:1px solid #C89B3C;"
                    "border-radius:3px; color:#C89B3C; font-weight:bold;")
        else:
            label.setText(name[:2].upper() if name else "?")
            label.setStyleSheet(
                "background:#1E2A3A; border:1px solid #C89B3C;"
                "border-radius:3px; color:#C89B3C; font-weight:bold;")

        layout.addWidget(label)
        return wrap

    def _make_build_widget(self, items: list) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for item in items[:5]:   # показываем не более 5 иконок
            lbl = QLabel()
            lbl.setFixedSize(36, 36)
            lbl.setToolTip(item.name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if item.icon_path:
                full = os.path.join(BASE_DIR, item.icon_path) \
                    if not os.path.isabs(item.icon_path) else item.icon_path
                if os.path.exists(full):
                    pix = QPixmap(full).scaled(
                        34, 34,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    lbl.setPixmap(pix)
                    lbl.setStyleSheet(
                        "border:1px solid #3A4A5A; border-radius:3px;")
                else:
                    lbl.setText(item.name[:3])
                    lbl.setStyleSheet(
                        "background:#1E2A3A; border:1px solid #3A4A5A;"
                        "border-radius:3px; color:#8A9AB0; font-size:9px;")
            else:
                lbl.setText(item.name[:3])
                lbl.setStyleSheet(
                    "background:#1E2A3A; border:1px solid #3A4A5A;"
                    "border-radius:3px; color:#8A9AB0; font-size:9px;")
            layout.addWidget(lbl)

        layout.addStretch()
        return wrap

    # ── Действия ──────────────────────────────────────────────────────────────

    def _get_selected_champ_idx(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return None
        item = self.table.item(row, 1)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_double_click(self):
        self._edit_selected()

    def _edit_selected(self):
        idx = self._get_selected_champ_idx()
        if idx is not None:
            self.editRequested.emit(idx)

    def _delete_selected(self):
        idx = self._get_selected_champ_idx()
        if idx is not None:
            self.deleteRequested.emit(idx)
