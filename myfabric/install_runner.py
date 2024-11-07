import subprocess
import os

def run_install():
    install_script = os.path.join(os.path.dirname(__file__), 'install.sh')
    if os.path.exists(install_script):
        subprocess.run(['bash', install_script], check=True)
    else:
        print("Ошибка: Скрипт install.sh не найден")
