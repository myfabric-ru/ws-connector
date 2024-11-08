# -*- coding: utf-8 -*-
import subprocess
import os


def run_install():
    install_script = os.path.join(os.path.dirname(__file__), 'install.sh')
    if os.path.exists(install_script):
        # Используем subprocess.call для совместимости с Python 2
        result = subprocess.call(['bash', install_script])
        if result != 0:
            print("Ошибка: выполнение скрипта install.sh завершилось с ошибкой.")
    else:
        print("Ошибка: Скрипт install.sh не найден")


def run_uninstall(printer_key):
    uninstall_script = os.path.join(os.path.dirname(__file__), 'uninstall.sh')
    if os.path.exists(uninstall_script):
        # Используем subprocess.call для совместимости с Python 2
        result = subprocess.call(['bash', uninstall_script, printer_key])
        if result != 0:
            print("Ошибка: выполнение скрипта uninstall.sh завершилось с ошибкой.")
    else:
        print("Ошибка: Скрипт uninstall.sh не найден")
