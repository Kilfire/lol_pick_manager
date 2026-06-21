"""
Система переводов интерфейса (RU / EN).

Использование:
    from core.i18n import tr, lang_manager

    label = QLabel(tr("preset_label"))

    # Переключение языка:
    lang_manager.set_language("en")

Виджеты, которые должны обновляться при смене языка, регистрируют функцию
обратного вызова через lang_manager.add_listener(callback).
"""
import json
import os
from typing import Callable

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_LANGUAGE = "ru"

# ── Словарь переводов ────────────────────────────────────────────────────────
# Ключ -> {"ru": "...", "en": "..."}

TRANSLATIONS: dict[str, dict[str, str]] = {

    # ── Общие ───────────────────────────────────────────────────────────────
    "app_title":        {"ru": "⚔  LoL Picks Manager",              "en": "⚔  LoL Picks Manager"},
    "language":          {"ru": "Язык",                              "en": "Language"},

    # ── Меню ────────────────────────────────────────────────────────────────
    "menu_file":         {"ru": "Файл",                              "en": "File"},
    "menu_new_preset":   {"ru": "Новый пресет",                      "en": "New preset"},
    "menu_save_local":   {"ru": "Сохранить пресет (JSON)",           "en": "Save preset (JSON)"},
    "menu_load_local":   {"ru": "Открыть пресет (JSON)...",          "en": "Open preset (JSON)..."},
    "menu_quit":         {"ru": "Выход",                             "en": "Quit"},
    "menu_cloud":        {"ru": "☁ Google Sheets",                   "en": "☁ Google Sheets"},
    "menu_cloud_manage": {"ru": "Управление Google Sheets...",       "en": "Manage Google Sheets..."},
    "menu_cloud_save":   {"ru": "Сохранить текущий пресет → Sheets", "en": "Save current preset → Sheets"},
    "menu_champions":    {"ru": "Чемпионы",                          "en": "Champions"},
    "menu_add_champion": {"ru": "Добавить чемпиона",                 "en": "Add champion"},
    "menu_help":         {"ru": "Справка",                           "en": "Help"},
    "menu_about":        {"ru": "О программе",                       "en": "About"},

    # ── Левая панель ────────────────────────────────────────────────────────
    "presets_title":     {"ru": "ПРЕСЕТЫ",                           "en": "PRESETS"},
    "btn_new_preset":    {"ru": "+ Новый пресет",                    "en": "+ New preset"},
    "btn_load_json":     {"ru": "📂 Загрузить JSON",                 "en": "📂 Load JSON"},
    "btn_save_json":     {"ru": "💾 Сохранить JSON",                 "en": "💾 Save JSON"},
    "btn_save_sheets":   {"ru": "☁ Сохранить→Sheets",                "en": "☁ Save→Sheets"},
    "btn_delete_preset": {"ru": "✕ Удалить пресет",                  "en": "✕ Delete preset"},
    "info_title":        {"ru": "ИНФО",                              "en": "INFO"},
    "champ_count":       {"ru": "Чемпионов: {n}",                    "en": "Champions: {n}"},

    # ── Правая панель / таблица ────────────────────────────────────────────
    "select_preset":     {"ru": "Выберите пресет",                   "en": "Select a preset"},
    "btn_add_champion":  {"ru": "+ Добавить чемпиона",                "en": "+ Add champion"},
    "filter_role":       {"ru": "Роль:",                             "en": "Role:"},
    "filter_class":      {"ru": "Класс урона:",                      "en": "Damage class:"},
    "filter_tier":       {"ru": "Тир:",                              "en": "Tier:"},
    "filter_search":     {"ru": "Поиск:",                            "en": "Search:"},
    "filter_search_ph":  {"ru": "Имя чемпиона...",                   "en": "Champion name..."},
    "btn_reset_filter":  {"ru": "✕ Сбросить",                        "en": "✕ Reset"},
    "all_roles":         {"ru": "Все роли",                          "en": "All roles"},
    "all_classes":       {"ru": "Все классы",                        "en": "All classes"},
    "all_tiers":         {"ru": "Все тиры",                          "en": "All tiers"},
    "btn_edit":          {"ru": "✏ Редактировать",                   "en": "✏ Edit"},
    "btn_delete":        {"ru": "🗑 Удалить",                        "en": "🗑 Delete"},
    "stats_shown":       {"ru": "Показано: {shown} из {total} чемпионов  •  отсортировано по роли и классу урона",
                           "en": "Shown: {shown} of {total} champions  •  sorted by role and damage class"},

    # ── Колонки таблицы ─────────────────────────────────────────────────────
    "col_icon":          {"ru": "Иконка",                            "en": "Icon"},
    "col_name":          {"ru": "Имя",                                "en": "Name"},
    "col_role":          {"ru": "Роль",                               "en": "Role"},
    "col_class":         {"ru": "Класс урона",                        "en": "Damage class"},
    "col_detailed":      {"ru": "Подробный тип",                      "en": "Detailed type"},
    "col_build":         {"ru": "Основной билд",                      "en": "Core build"},
    "col_situational":   {"ru": "Ситуативные",                        "en": "Situational"},
    "col_tier":          {"ru": "Тир",                                "en": "Tier"},
    "col_notes":         {"ru": "Заметки",                            "en": "Notes"},

    # ── Роли (позиции) ──────────────────────────────────────────────────────
    "role_top":          {"ru": "Топ",  "en": "Top"},
    "role_jungle":        {"ru": "Лес",  "en": "Jungle"},
    "role_mid":          {"ru": "Мид",  "en": "Mid"},
    "role_adc":          {"ru": "Адк",  "en": "ADC"},
    "role_support":      {"ru": "Сап",  "en": "Support"},

    # ── Классы урона ────────────────────────────────────────────────────────
    "class_ad":          {"ru": "АД",       "en": "AD"},
    "class_ap":          {"ru": "АП",       "en": "AP"},
    "class_tank":        {"ru": "Танк",     "en": "Tank"},
    "class_utility":     {"ru": "Утилити", "en": "Utility"},
    "class_hybrid":      {"ru": "Гибрид",  "en": "Hybrid"},

    # ── Диалог чемпиона ─────────────────────────────────────────────────────
    "champion_dialog_title":      {"ru": "Чемпион",                  "en": "Champion"},
    "champion_dialog_edit_title": {"ru": "Редактирование: {name}",   "en": "Editing: {name}"},
    "btn_pick_icon":               {"ru": "🖼 Выбрать иконку",         "en": "🖼 Choose icon"},
    "label_name":                  {"ru": "Имя:",                     "en": "Name:"},
    "name_placeholder":            {"ru": "Введите имя чемпиона",     "en": "Enter champion name"},
    "label_role":                  {"ru": "Роль (позиция):",          "en": "Role (position):"},
    "label_class":                 {"ru": "Класс урона:",             "en": "Damage class:"},
    "label_detailed":              {"ru": "Подробный тип:",           "en": "Detailed type:"},
    "label_tier":                  {"ru": "Место в тирлисте:",        "en": "Tier placement:"},
    "group_build_core":            {"ru": "🗡️ Основной билд",         "en": "🗡️ Core build"},
    "group_build_sit":             {"ru": "⚡ Ситуативные предметы",   "en": "⚡ Situational items"},
    "btn_add_item":                {"ru": "+ Добавить предмет",       "en": "+ Add item"},
    "item_name_ph":                {"ru": "Название предмета",        "en": "Item name"},
    "group_notes":                 {"ru": "📝 Заметки",                "en": "📝 Notes"},
    "notes_placeholder":           {"ru": "Сильные стороны, слабые стороны, советы по пику...",
                                     "en": "Strengths, weaknesses, pick advice..."},
    "btn_confirm_save":            {"ru": "✔ Сохранить",              "en": "✔ Save"},
    "btn_cancel":                  {"ru": "Отмена",                   "en": "Cancel"},

    # ── Диалог выбора иконки ────────────────────────────────────────────────
    "icon_picker_title_champ":     {"ru": "Выбор иконки чемпиона",    "en": "Choose champion icon"},
    "icon_picker_title_item":      {"ru": "Выбор иконки предмета",    "en": "Choose item icon"},
    "icon_search_ph":               {"ru": "Например: Aatrox, Jinx, Yasuo...",
                                      "en": "E.g.: Aatrox, Jinx, Yasuo..."},
    "btn_browse_external":          {"ru": "📂 Найти файл вне галереи...",
                                      "en": "📂 Browse outside gallery..."},
    "btn_select":                    {"ru": "✔ Выбрать",               "en": "✔ Select"},
    "icons_found":                   {"ru": "Найдено иконок: {n}",     "en": "Icons found: {n}"},
    "no_icons_in_folder":            {"ru": "В папке {folder}/ пока нет иконок. Можно выбрать файл вручную кнопкой «Найти файл вне галереи».",
                                       "en": "No icons in {folder}/ yet. You can pick a file manually using \"Browse outside gallery\"."},

    # ── Google Sheets диалог ────────────────────────────────────────────────
    "gsheets_title":                {"ru": "☁ Google Sheets",         "en": "☁ Google Sheets"},
    "gsheets_setup_group":          {"ru": "Настройка подключения",    "en": "Connection setup"},
    "gsheets_cred_not_found":        {"ru": "service_account.json: не найден",
                                       "en": "service_account.json: not found"},
    "gsheets_cred_found":            {"ru": "service_account.json: ✅ найден",
                                       "en": "service_account.json: ✅ found"},
    "gsheets_bot_email":              {"ru": "Email сервисного аккаунта: —",
                                        "en": "Service account email: —"},
    "btn_pick_credentials":           {"ru": "📁 Выбрать service_account.json",
                                        "en": "📁 Choose service_account.json"},
    "btn_howto":                      {"ru": "? Как настроить?",         "en": "? How to set up?"},
    "label_spreadsheet_id":           {"ru": "ID таблицы:",              "en": "Spreadsheet ID:"},
    "btn_save_spreadsheet_id":         {"ru": "💾 Сохранить ID таблицы", "en": "💾 Save spreadsheet ID"},
    "gsheets_conn_group":              {"ru": "Подключение",             "en": "Connection"},
    "gsheets_not_connected":           {"ru": "Не подключено",           "en": "Not connected"},
    "gsheets_connected":               {"ru": "✅ Подключено к Google Sheets",
                                         "en": "✅ Connected to Google Sheets"},
    "gsheets_disconnected_status":     {"ru": "❌ Не подключено",         "en": "❌ Not connected"},
    "btn_connect":                     {"ru": "🔗 Подключиться",         "en": "🔗 Connect"},
    "btn_disconnect":                  {"ru": "Отключиться",             "en": "Disconnect"},
    "btn_open_sheet":                  {"ru": "🌐 Открыть таблицу",      "en": "🌐 Open spreadsheet"},
    "gsheets_presets_group":            {"ru": "☁ Пресеты в Google Sheets",
                                          "en": "☁ Presets in Google Sheets"},
    "btn_refresh_list":                  {"ru": "🔄 Обновить список",    "en": "🔄 Refresh list"},
    "btn_load_preset":                   {"ru": "⬇ Загрузить пресет",   "en": "⬇ Load preset"},
    "btn_delete_preset_cloud":            {"ru": "✕ Удалить пресет",     "en": "✕ Delete preset"},
    "gsheets_log_group":                  {"ru": "Журнал",               "en": "Log"},
    "btn_close":                           {"ru": "Закрыть",              "en": "Close"},

    # ── Статус-бар ───────────────────────────────────────────────────────────
    "status_ready":                        {"ru": "Готово  |  LoL Picks Manager",
                                             "en": "Ready  |  LoL Picks Manager"},
    "status_preset_info":                  {"ru": "Пресет: {name}  •  {n} чемпионов",
                                             "en": "Preset: {name}  •  {n} champions"},

    # ── Тип команды ──────────────────────────────────────────────────────────
    "team_ours":         {"ru": "Наша команда",  "en": "Our team"},
    "team_enemy":        {"ru": "Противники",     "en": "Opponents"},
}


class LanguageManager:
    """Хранит текущий выбранный язык, уведомляет подписчиков об изменениях."""

    def __init__(self):
        self._language = self._load_saved_language()
        self._listeners: list[Callable[[], None]] = []

    # ── Сохранение/загрузка ──────────────────────────────────────────────────

    def _load_saved_language(self) -> str:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                lang = cfg.get("language", DEFAULT_LANGUAGE)
                if lang in ("ru", "en"):
                    return lang
            except Exception:
                pass
        return DEFAULT_LANGUAGE

    def _save_language(self):
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
        cfg["language"] = self._language
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    # ── Публичный API ─────────────────────────────────────────────────────────

    def get_language(self) -> str:
        return self._language

    def set_language(self, language: str):
        if language not in ("ru", "en"):
            return
        if language == self._language:
            return
        self._language = language
        self._save_language()
        for callback in self._listeners:
            try:
                callback()
            except Exception:
                pass

    def add_listener(self, callback: Callable[[], None]):
        """Регистрирует функцию, которая будет вызвана при смене языка
        (обычно — метод обновления текстов в виджете)."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def translate(self, key: str, **kwargs) -> str:
        entry = TRANSLATIONS.get(key)
        if entry is None:
            return key   # fallback — показываем сам ключ, чтобы было видно, что перевод не найден
        text = entry.get(self._language, entry.get(DEFAULT_LANGUAGE, key))
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return text


# Глобальный экземпляр
lang_manager = LanguageManager()


def tr(key: str, **kwargs) -> str:
    """Короткая функция перевода: tr("btn_save_json")"""
    return lang_manager.translate(key, **kwargs)
