# -*- coding: utf-8 -*-
import subprocess
import os


def run_install():
    install_script = os.path.join(os.path.dirname(__file__), 'install.sh')
    if os.path.exists(install_script):
        subprocess.run(['bash', install_script], check=True)
    else:
        print("Ошибка: Скрипт install.sh не найден")


def run_uninstall(printer_key):
    uninstall_script = os.path.join(os.path.dirname(__file__), 'uninstall.sh')
    if os.path.exists(uninstall_script):
        subprocess.run(['bash', uninstall_script, printer_key], check=True)
    else:
        print("Ошибка: Скрипт uninstall.sh не найден")
