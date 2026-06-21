"""
LoL Picks Manager — Tournament Pick/Ban Tool
Главная точка входа в приложение
"""
import sys
import os

# Добавляем директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LoL Picks Manager")
    app.setOrganizationName("Tournament Tools")

    # Загружаем стили
    style_path = os.path.join(os.path.dirname(__file__), "ui", "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
