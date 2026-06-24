"""
Модели данных для чемпионов и пресетов
"""
from dataclasses import dataclass, field
from typing import List, Optional
import json
import os

# ── Константы ──────────────────────────────────────────────────────────────────

# Роль на карте (позиция)
ROLES = ["Топ", "Лес", "Мид", "Адк", "Сап", "Замена"]

# Класс урона / архетип чемпиона
DAMAGE_CLASSES = ["АД", "АП", "Танк", "Утилити", "Гибрид"]

# Подробный тип урона — зависит от класса урона
DETAILED_DAMAGE_TYPES = {
    "АД":      ["Физический", "Критический", "Онхит"],
    "АП":      ["Магический", "Burst", "DOT"],
    "Танк":    ["Frontline", "CC-танк", "Engage"],
    "Утилити": ["Хилер/Щит", "Peeler", "Engage", "CC"],
    "Гибрид":  ["Гибрид Физ/Маг", "True Damage", "Смешанный"],
}

TIER_LIST = ["S", "A", "B", "C"]

# Порядок сортировки (индекс в списке = приоритет сортировки)
ROLE_ORDER = {role: i for i, role in enumerate(ROLES)}
DAMAGE_CLASS_ORDER = {dc: i for i, dc in enumerate(DAMAGE_CLASSES)}
TIER_ORDER = {t: i for i, t in enumerate(TIER_LIST)}

# Цвета классов урона (используются для текста чипа в таблице).
# Фон у всех чипов одинаковый — тёмный/чёрный, отличается только цвет текста/обводки.
DAMAGE_CLASS_COLORS = {
    "АД":      "#E74C3C",   # красный текст
    "АП":      "#3498DB",   # синий текст
    "Танк":    "#2ECC71",   # зелёный текст
    "Утилити": "#F39C12",   # оранжевый текст
    "Гибрид":  "#9B59B6",   # фиолетовый текст
}

# Обратная совместимость со старым названием (на случу если где-то ещё используется)
ROLE_COLORS = DAMAGE_CLASS_COLORS

# ── Отображаемые имена для UI (перевод) ─────────────────────────────────────
# ВАЖНО: внутренние значения (то, что хранится в JSON / Google Sheets) остаются
# русскими строками ("Топ", "АД" и т.д.) для обратной совместимости со всеми
# уже сохранёнными пресетами. Эти словари используются ТОЛЬКО для отображения
# подписи на нужном языке интерфейса — сама логика и сортировка продолжают
# работать с исходным (русским) ключом.

ROLE_DISPLAY_KEYS = {
    "Топ": "role_top",
    "Лес": "role_jungle",
    "Мид": "role_mid",
    "Адк": "role_adc",
    "Сап": "role_support",
}

DAMAGE_CLASS_DISPLAY_KEYS = {
    "АД":      "class_ad",
    "АП":      "class_ap",
    "Танк":    "class_tank",
    "Утилити": "class_utility",
    "Гибрид":  "class_hybrid",
}


def role_display(role: str) -> str:
    """Возвращает локализованное имя роли для текущего языка интерфейса."""
    from core.i18n import tr
    key = ROLE_DISPLAY_KEYS.get(role)
    return tr(key) if key else role


def damage_class_display(damage_class: str) -> str:
    """Возвращает локализованное имя класса урона для текущего языка интерфейса."""
    from core.i18n import tr
    key = DAMAGE_CLASS_DISPLAY_KEYS.get(damage_class)
    return tr(key) if key else damage_class


TEAM_TYPE_DISPLAY_KEYS = {
    "Наша команда": "team_ours",
    "Противники":   "team_enemy",
}


def team_type_display(team_type: str) -> str:
    """Возвращает локализованное имя типа команды для текущего языка интерфейса."""
    from core.i18n import tr
    key = TEAM_TYPE_DISPLAY_KEYS.get(team_type)
    return tr(key) if key else team_type

# ── Дата-классы ────────────────────────────────────────────────────────────────

@dataclass
class BuildItem:
    name: str
    icon_path: str = ""   # относительный путь: icons/items/<name>.png


@dataclass
class Champion:
    name: str
    role: str                          # позиция: Топ/Лес/Мид/Адк/Сап
    damage_class: str = ""             # класс урона: АД/АП/Танк/Утилити/Гибрид
    damage_type: str = ""              # подробный тип: Физический/Критический/...
    tier: str = "B"
    icon_path: str = ""                # icons/champions/<name>.png
    build_core: List[BuildItem] = field(default_factory=list)
    build_situational: List[BuildItem] = field(default_factory=list)
    notes: str = ""

    # ── сериализация ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name":         self.name,
            "role":         self.role,
            "damage_class": self.damage_class,
            "damage_type":  self.damage_type,
            "tier":         self.tier,
            "icon_path":    self.icon_path,
            "build_core": [{"name": b.name, "icon_path": b.icon_path}
                           for b in self.build_core],
            "build_situational": [{"name": b.name, "icon_path": b.icon_path}
                                  for b in self.build_situational],
            "notes":        self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Champion":
        return cls(
            name         = d.get("name", ""),
            role         = d.get("role", ROLES[0]),
            damage_class = d.get("damage_class", DAMAGE_CLASSES[0]),
            damage_type  = d.get("damage_type", ""),
            tier         = d.get("tier", "B"),
            icon_path    = d.get("icon_path", ""),
            build_core   = [BuildItem(**b) for b in d.get("build_core", [])],
            build_situational = [BuildItem(**b)
                                 for b in d.get("build_situational", [])],
            notes        = d.get("notes", ""),
        )

    # ── ключ сортировки ──────────────────────────────────────────────────────

    def sort_key(self):
        """Сортировка: сначала по роли (Топ→Сап), затем по классу урона (АД→Гибрид)."""
        return (
            ROLE_ORDER.get(self.role, 99),
            TIER_ORDER.get(self.tier, 99),
            DAMAGE_CLASS_ORDER.get(self.damage_class, 99),
            self.name.lower(),
        )


@dataclass
class Preset:
    name: str
    team_type: str = "Наша команда"   # "Наша команда" / "Противники"
    champions: List[Champion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name":      self.name,
            "team_type": self.team_type,
            "champions": [c.to_dict() for c in self.champions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Preset":
        return cls(
            name      = d.get("name", "Новый пресет"),
            team_type = d.get("team_type", "Наша команда"),
            champions = [Champion.from_dict(c) for c in d.get("champions", [])],
        )

    def sorted_champions(self) -> List[Champion]:
        """Возвращает чемпионов, отсортированных по роли → классу урона → тиру → имени."""
        return sorted(self.champions, key=lambda c: c.sort_key())

    def save_local(self, directory: str) -> str:
        """Сохраняет пресет в JSON-файл. Возвращает путь."""
        os.makedirs(directory, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_"
                            for c in self.name).strip()
        path = os.path.join(directory, f"{safe_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load_local(cls, path: str) -> "Preset":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ── Примеры пресетов для быстрого старта ───────────────────────────────────────

def get_example_presets() -> List[Preset]:
    our = Preset(
        name="Наша команда",
        team_type="Наша команда",
        champions=[
            Champion(
                name="Jinx",
                role="Адк",
                damage_class="АД",
                damage_type="Критический",
                tier="S",
                icon_path="icons/champions/Jinx.png",
                build_core=[
                    BuildItem("Kraken Slayer",   "icons/items/KrakenSlayer.png"),
                    BuildItem("Runaan's Hurricane","icons/items/RunaansHurricane.png"),
                    BuildItem("Infinity Edge",    "icons/items/InfinityEdge.png"),
                ],
                build_situational=[
                    BuildItem("Mortal Reminder", "icons/items/MortalReminder.png"),
                ],
                notes="Сильный поздний пик, нужна защита",
            ),
            Champion(
                name="Lux",
                role="Мид",
                damage_class="АП",
                damage_type="Burst",
                tier="A",
                icon_path="icons/champions/Lux.png",
                build_core=[
                    BuildItem("Luden's Tempest",  "icons/items/LudensTempest.png"),
                    BuildItem("Shadowflame",       "icons/items/Shadowflame.png"),
                ],
                build_situational=[
                    BuildItem("Zhonya's Hourglass","icons/items/ZhonyasHourglass.png"),
                ],
                notes="Хороший контроль, уязвима к gap-close",
            ),
            Champion(
                name="Malphite",
                role="Топ",
                damage_class="Танк",
                damage_type="Engage",
                tier="S",
                icon_path="icons/champions/Malphite.png",
                build_core=[
                    BuildItem("Sunfire Aegis", "icons/items/SunfireAegis.png"),
                    BuildItem("Thornmail",     "icons/items/Thornmail.png"),
                ],
                build_situational=[
                    BuildItem("Randuin's Omen","icons/items/RanduinsOmen.png"),
                ],
                notes="Идеален против AD-compose",
            ),
            Champion(
                name="Soraka",
                role="Сап",
                damage_class="Утилити",
                damage_type="Хилер/Щит",
                tier="A",
                icon_path="icons/champions/Soraka.png",
                build_core=[
                    BuildItem("Moonstone Renewer","icons/items/MoonstoneRenewer.png"),
                    BuildItem("Redemption",       "icons/items/Redemption.png"),
                ],
                build_situational=[
                    BuildItem("Mikael's Blessing","icons/items/MikaelsBlessing.png"),
                ],
                notes="Глобальный хил, слабая к engage",
            ),
            Champion(
                name="Kayle",
                role="Топ",
                damage_class="Гибрид",
                damage_type="Гибрид Физ/Маг",
                tier="B",
                icon_path="icons/champions/Kayle.png",
                build_core=[
                    BuildItem("Nashor's Tooth",  "icons/items/NashorsTooth.png"),
                    BuildItem("Kraken Slayer",   "icons/items/KrakenSlayer.png"),
                ],
                build_situational=[
                    BuildItem("Rabadon's Deathcap","icons/items/RabadonsDeathcap.png"),
                ],
                notes="Слабо в ранней — сильно в поздней игре",
            ),
            Champion(
                name="Lee Sin",
                role="Лес",
                damage_class="АД",
                damage_type="Онхит",
                tier="B",
                icon_path="icons/champions/LeeSin.png",
                build_core=[
                    BuildItem("Goredrinker", "icons/items/Goredrinker.png"),
                ],
                build_situational=[],
                notes="Сильный ранний газ",
            ),
        ],
    )

    enemy = Preset(
        name="Противники — Турнир",
        team_type="Противники",
        champions=[
            Champion(
                name="Caitlyn",
                role="Адк",
                damage_class="АД",
                damage_type="Критический",
                tier="A",
                icon_path="icons/champions/Caitlyn.png",
                build_core=[
                    BuildItem("Galeforce",     "icons/items/Galeforce.png"),
                    BuildItem("Infinity Edge", "icons/items/InfinityEdge.png"),
                ],
                build_situational=[
                    BuildItem("Lord Dominik's","icons/items/LordDominiks.png"),
                ],
                notes="Сильный лейн, слабее в файтах",
            ),
            Champion(
                name="Viktor",
                role="Мид",
                damage_class="АП",
                damage_type="DOT",
                tier="S",
                icon_path="icons/champions/Viktor.png",
                build_core=[
                    BuildItem("Luden's Tempest","icons/items/LudensTempest.png"),
                    BuildItem("Void Staff",     "icons/items/VoidStaff.png"),
                ],
                build_situational=[],
                notes="Топ мид-лейнер, стабильный урон",
            ),
        ],
    )

    return [our, enemy]
