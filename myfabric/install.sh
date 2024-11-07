#!/bin/bash

CURRENT_USER=$(whoami)

CONNECT_PATH=$(which myfabric-connector)

# Если не найдено в $PATH, попробуем поискать в стандартных директориях
if [[ -z "$CONNECT_PATH" ]]; then
    # Проверяем ~/.local/bin и ~/.local/bin для пользователя
    if [[ -x "$HOME/.local/bin/myfabric-connector" ]]; then
        CONNECT_PATH="$HOME/.local/bin/myfabric-connector"
    elif [[ -x "/usr/local/bin/myfabric-connector" ]]; then
        CONNECT_PATH="/usr/local/bin/myfabric-connector"
    else
        # Запрос пути у пользователя, если не найден
        read -p "Не удалось найти myfabric-connector в стандартных директориях. Укажите полный путь: " user_path
        if [[ -x "$user_path" ]]; then
            CONNECT_PATH="$user_path"
        else
            echo "Ошибка: указанный путь ($user_path) не является исполняемым файлом."
            exit 1
        fi
    fi
fi

# Функция для создания файлов окружения и служб systemd
function setup_service {
    local printer_key=$1
    local moonraker_url=$2

    # Создание файла окружения
    local env_file="/etc/myfabric/myfabric_$printer_key.conf"
    sudo mkdir -p $(dirname $env_file)
    echo "MOONRAKER_URL=$moonraker_url" | sudo tee $env_file
    echo "PRINTER_KEY=$printer_key" | sudo tee -a $env_file
    echo "MYFABRIC_LOGIN=$myfabric_email" | sudo tee -a $env_file
    echo "MYFABRIC_PASSWORD=$myfabric_password" | sudo tee -a $env_file
    echo "LOG_FILE=/var/log/myfabric/myfabric_$printer_key.log" | sudo tee -a $env_file
    echo "LOG_LEVEL=INFO" | sudo tee -a $env_file
    sudo chmod 600 $env_file
    sudo chown root:root $env_file

    # Создание и активация systemd службы
    local service_file="/etc/systemd/system/myfabric_$printer_key.service"
    echo "[Unit]
Description=MyFabric Connector Service for $printer_key
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
EnvironmentFile=$env_file
ExecStart=$CONNECT_PATH start \$MOONRAKER_URL \$PRINTER_KEY \$MYFABRIC_LOGIN \$MYFABRIC_PASSWORD --log-file \$LOG_FILE --log-level \$LOG_LEVEL
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target" | sudo tee $service_file

    sudo systemctl daemon-reload
    sudo systemctl enable myfabric_$printer_key.service
    sudo systemctl restart myfabric_$printer_key.service
}

echo "Сбор информации для установки..."

# Запрос общих данных
read -p "Введите email для MyFabric: " myfabric_email
read -sp "Введите пароль для MyFabric: " myfabric_password
echo

# Запрос данных по каждому принтеру
declare -a printer_keys
declare -a moonraker_urls

while true; do
    read -p "Введите printer key: " printer_key
    read -p "Введите URL Moonraker для принтера $printer_key (например, localhost:7125): " moonraker_url

    printer_keys+=("$printer_key")
    moonraker_urls+=("$moonraker_url")

    read -p "Добавить еще принтер? (Y/N): " add_more
    if [[ "$add_more" =~ ^(Нет|нет|n|N)$ ]]; then
        break
    fi
done

# Создание каталога для логов
sudo mkdir -p /var/log/myfabric
sudo chown "$CURRENT_USER":"$CURRENT_USER" /var/log/myfabric
sudo chmod 775 -R /var/log/myfabric

# Настройка служб для каждого принтера
for i in "${!printer_keys[@]}"; do
    setup_service "${printer_keys[$i]}" "${moonraker_urls[$i]}"
done

echo "Установка и настройка завершены. Службы запущены."
