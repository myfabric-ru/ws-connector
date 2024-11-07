#!/bin/bash

if [[ -z "$1" ]]; then
    echo "Ошибка: Укажите printer key для удаления службы."
    exit 1
fi

printer_key=$1
service_name="myfabric_$printer_key.service"
env_file="/etc/myfabric/myfabric_$printer_key.conf"
log_file="/var/log/myfabric/myfabric_$printer_key.log"

# Остановка и отключение службы
echo "Остановка и удаление службы $service_name..."
sudo systemctl stop "$service_name"
sudo systemctl disable "$service_name"

# Удаление файла службы
sudo rm -f "/etc/systemd/system/$service_name"
sudo systemctl daemon-reload

# Удаление файла конфигурации и лога
echo "Удаление конфигурационного файла и лога..."
sudo rm -f "$env_file"
sudo rm -f "$log_file"

echo "Служба и связанные файлы для принтера с ключом $printer_key успешно удалены."
