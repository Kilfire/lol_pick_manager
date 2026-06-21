"""
Google Sheets интеграция через СЕРВИСНЫЙ АККАУНТ.

Почему сервисный аккаунт, а не OAuth (InstalledAppFlow):
  • OAuth требует, чтобы при ПЕРВОМ запуске открылся браузер и человек вручную
    залогинился под СВОИМ Google-аккаунтом. На безголовых/удалённых машинах,
    либо если браузер не может открыться, это приводит к зависанию и таймауту
    (что и было причиной ошибки "Read timed out").
  • Сервисный аккаунт — это "робот"-аккаунт Google. Он не требует входа в браузере:
    у него есть собственный JSON-ключ (приватный ключ + email), которым программа
    подписывает запросы напрямую. Поэтому ЛЮБОЙ человек с этой программой и с файлом
    ключа сразу подключается к общей таблице — без браузера, без ожидания.

Как подключить (один раз настраивает капитан/администратор):
  1. console.cloud.google.com → создать проект → включить
     "Google Sheets API" и "Google Drive API"
  2. IAM и администрирование → Сервисные аккаунты → Создать сервисный аккаунт
  3. Открыть аккаунт → вкладка "Ключи" → Добавить ключ → JSON → скачать файл
  4. Положить скачанный файл рядом с main.py и назвать его:
         service_account.json
  5. Открыть Google-таблицу → "Поделиться" → вставить email сервисного
     аккаунта (вида xxx@yyy.iam.gserviceaccount.com, он есть внутри JSON-файла
     в поле "client_email") → роль "Редактор"
  6. Скопировать ID таблицы из адресной строки браузера:
         https://docs.google.com/spreadsheets/d/  ВОТ_ЭТО_ID  /edit
     и вставить его в файл config.json (создаётся автоматически при первом
     запуске, либо см. README) в поле "spreadsheet_id"

После этого ВСЕ члены команды, у которых есть service_account.json и тот же
spreadsheet_id, подключаются к ОДНОЙ И ТОЙ ЖЕ таблице мгновенно.

ВАЖНО О БЕЗОПАСНОСТИ:
  service_account.json — это секретный ключ, по сути "пароль" от бота с правами
  на запись. Никогда не публикуйте его в открытых репозиториях/чатах. Если ключ
  случайно "засветился" — удалите его в Google Cloud Console (Keys → Delete) и
  создайте новый.
"""
import json
import os
from typing import List, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from core.models import Champion, Preset, BuildItem, ROLES, DAMAGE_CLASSES

# ── Константы ──────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "service_account.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Время ожидания ответа от Google API (секунды).
# Без этого зависший запрос мог висеть бесконечно (read timeout=None),
# из-за чего интерфейс программы "замораживался".
REQUEST_TIMEOUT = 15

# Колонки таблицы
HEADERS = [
    "name", "role", "damage_class", "damage_type", "tier", "icon_path",
    "build_core", "build_situational", "notes", "team_type",
]


def _build_items_to_str(items: list) -> str:
    """Сериализует список BuildItem в строку JSON для хранения в ячейке."""
    return json.dumps([{"name": b.name, "icon_path": b.icon_path} for b in items],
                      ensure_ascii=False)


def _str_to_build_items(s: str) -> list:
    if not s:
        return []
    try:
        data = json.loads(s)
        return [BuildItem(**d) for d in data]
    except Exception:
        return []


def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class GoogleSheetsManager:
    """Управляет синхронизацией пресетов с Google Sheets через сервисный аккаунт."""

    def __init__(self):
        self._gc: Optional["gspread.Client"] = None
        self._spreadsheet = None
        self._connected = False

    # ── Подключение ────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return GSPREAD_AVAILABLE

    def is_connected(self) -> bool:
        return self._connected

    def has_service_account_file(self) -> bool:
        return os.path.exists(SERVICE_ACCOUNT_FILE)

    def get_spreadsheet_id(self) -> str:
        return _load_config().get("spreadsheet_id", "")

    def set_spreadsheet_id(self, spreadsheet_id: str):
        cfg = _load_config()
        cfg["spreadsheet_id"] = spreadsheet_id.strip()
        _save_config(cfg)

    def get_service_account_email(self) -> str:
        """Читает client_email из ключа — удобно показать пользователю,
        кому нужно дать доступ к таблице."""
        if not self.has_service_account_file():
            return ""
        try:
            with open(SERVICE_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("client_email", "")
        except Exception:
            return ""

    def connect(self) -> tuple[bool, str]:
        """
        Подключается к Google Sheets через сервисный аккаунт.
        Не открывает браузер, не ждёт ввода от пользователя — поэтому
        не подвержена зависанию/таймауту, характерному для OAuth-flow.
        Возвращает (success, message).
        """
        if not GSPREAD_AVAILABLE:
            return False, ("Библиотека gspread не установлена.\n"
                           "Запустите: pip install gspread google-auth")

        if not self.has_service_account_file():
            return False, (
                f"Файл service_account.json не найден рядом с программой.\n"
                f"Ожидаемый путь:\n{SERVICE_ACCOUNT_FILE}\n\n"
                "Получите его в Google Cloud Console → IAM → Сервисные аккаунты "
                "→ Ключи → Добавить ключ → JSON.")

        spreadsheet_id = self.get_spreadsheet_id()
        if not spreadsheet_id:
            return False, (
                "ID таблицы не задан.\n"
                "Откройте Google Sheets → скопируйте ID из адресной строки\n"
                "(часть между /d/ и /edit) и сохраните его через "
                "«☁ Google Sheets → Настройки подключения».")

        try:
            creds = ServiceAccountCredentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)

            # AuthorizedSession живёт в google.auth.transport.requests, а НЕ в
            # обычном модуле requests — это и было причиной ошибки
            # "module 'requests' has no attribute 'AuthorizedSession'".
            from google.auth.transport.requests import AuthorizedSession
            import requests
            session = AuthorizedSession(creds)
            session.request = _with_timeout(session.request, REQUEST_TIMEOUT)

            self._gc = gspread.Client(auth=creds, session=session)
            self._spreadsheet = self._gc.open_by_key(spreadsheet_id)
            self._connected = True
            return True, f"Подключено к таблице «{self._spreadsheet.title}»"

        except gspread.exceptions.APIError as e:
            msg = str(e)
            if "PERMISSION_DENIED" in msg or "403" in msg:
                email = self.get_service_account_email()
                return False, (
                    "Нет доступа к таблице (403).\n"
                    f"Откройте таблицу в браузере → «Поделиться» → добавьте:\n"
                    f"{email}\nс ролью «Редактор».")
            if "404" in msg:
                return False, "Таблица не найдена — проверьте правильность ID."
            return False, f"Ошибка Google API: {msg}"
        except requests.exceptions.Timeout:
            return False, (
                f"Превышено время ожидания ({REQUEST_TIMEOUT} сек).\n"
                "Проверьте подключение к интернету и повторите попытку.")
        except Exception as e:
            return False, f"Ошибка подключения: {e}"

    def disconnect(self):
        self._gc = None
        self._spreadsheet = None
        self._connected = False

    # ── Список пресетов ───────────────────────────────────────────────────────

    def list_presets(self) -> List[str]:
        """Возвращает список названий пресетов (листов) в таблице."""
        if not self._connected:
            return []
        try:
            return [ws.title for ws in self._spreadsheet.worksheets()]
        except Exception:
            return []

    # ── Вспомогательные ───────────────────────────────────────────────────────

    def _get_or_create_sheet(self, preset_name: str):
        """Возвращает лист с именем пресета (создаёт при отсутствии)."""
        try:
            return self._spreadsheet.worksheet(preset_name)
        except gspread.WorksheetNotFound:
            sheet = self._spreadsheet.add_worksheet(
                title=preset_name, rows=200, cols=len(HEADERS))
            sheet.append_row(HEADERS)
            return sheet

    # ── Сохранение ────────────────────────────────────────────────────────────

    def save_preset(self, preset: Preset) -> tuple[bool, str]:
        """Сохраняет пресет в Google Sheets (сортирует по роли → классу урона)."""
        if not self._connected:
            return False, "Нет подключения к Google Sheets"
        try:
            sheet = self._get_or_create_sheet(preset.name)
            sheet.clear()
            sheet.append_row(HEADERS)

            rows = []
            for champ in preset.sorted_champions():
                rows.append([
                    champ.name,
                    champ.role,
                    champ.damage_class,
                    champ.damage_type,
                    champ.tier,
                    champ.icon_path,
                    _build_items_to_str(champ.build_core),
                    _build_items_to_str(champ.build_situational),
                    champ.notes,
                    preset.team_type,
                ])
            if rows:
                sheet.append_rows(rows)

            url = f"https://docs.google.com/spreadsheets/d/{self._spreadsheet.id}"
            return True, f"Сохранено в Google Sheets\n{url}"

        except Exception as e:
            return False, f"Ошибка сохранения: {e}"

    # ── Загрузка ──────────────────────────────────────────────────────────────

    def load_preset(self, preset_name: str) -> tuple[Optional[Preset], str]:
        """Загружает пресет из Google Sheets."""
        if not self._connected:
            return None, "Нет подключения к Google Sheets"
        try:
            sheet = self._spreadsheet.worksheet(preset_name)
            records = sheet.get_all_records()

            champions = []
            team_type = "Наша команда"

            for r in records:
                team_type = r.get("team_type", "Наша команда") or team_type
                champ = Champion(
                    name         = r.get("name", ""),
                    role         = r.get("role", ROLES[0]),
                    damage_class = r.get("damage_class", DAMAGE_CLASSES[0]),
                    damage_type  = r.get("damage_type", ""),
                    tier         = r.get("tier", "B"),
                    icon_path    = r.get("icon_path", ""),
                    build_core        = _str_to_build_items(r.get("build_core", "")),
                    build_situational = _str_to_build_items(r.get("build_situational", "")),
                    notes        = r.get("notes", ""),
                )
                champions.append(champ)

            preset = Preset(
                name      = preset_name,
                team_type = team_type,
                champions = champions,
            )
            return preset, f"Загружено {len(champions)} чемпионов"

        except gspread.WorksheetNotFound:
            return None, f"Пресет «{preset_name}» не найден в таблице"
        except Exception as e:
            return None, f"Ошибка загрузки: {e}"

    def delete_preset(self, preset_name: str) -> tuple[bool, str]:
        """Удаляет лист (пресет) из таблицы."""
        if not self._connected:
            return False, "Нет подключения"
        try:
            sheet = self._spreadsheet.worksheet(preset_name)
            self._spreadsheet.del_worksheet(sheet)
            return True, f"Пресет «{preset_name}» удалён из Google Sheets"
        except Exception as e:
            return False, f"Ошибка удаления: {e}"

    def get_spreadsheet_url(self) -> str:
        if self._spreadsheet:
            return f"https://docs.google.com/spreadsheets/d/{self._spreadsheet.id}"
        spreadsheet_id = self.get_spreadsheet_id()
        if spreadsheet_id:
            return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        return ""


def _with_timeout(request_fn, timeout):
    """Оборачивает requests-сессию, чтобы у каждого запроса был жёсткий timeout
    и зависшее соединение не блокировало интерфейс программы навсегда."""
    def wrapped(*args, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return request_fn(*args, **kwargs)
    return wrapped


# Глобальный экземпляр
sheets_manager = GoogleSheetsManager()
