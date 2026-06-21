from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import AuthorizedSession

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_service_account_file("service_account.json", scopes=SCOPES)

print("Обновляем токен...")
auth_req = Request()
creds.refresh(auth_req)
print("Токен получен:", creds.token[:20], "...")

print("Подключаемся к Sheets...")
import gspread
session = AuthorizedSession(creds)
gc = gspread.Client(auth=creds, session=session)
sp = gc.open_by_key("1kFGXyIg13DdVI-2GxYHtBMW0K5znEkezitexhpmWX0s")
print("OK:", sp.title)
