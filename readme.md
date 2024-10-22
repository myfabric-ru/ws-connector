# MyFabric

Программа для проксирования данных с WebSocket Moonraker в CRM MyFabric.

## Установка

Текущая актуальная версия программы `0.1.30` работает с `Python 3`.

```bash
# Устанавливаем пакет на сервер с Moonraker
pip install myfabric-connector
```

## Команды

### Запуск проксирования

Запускаем программу, указав в качестве параметров URL WebSocket Moonraker, идентификатор принтера в системе MyFabric (channel_name), а также логин и пароль от учетной записи MyFabric в формате `email:password`.

```shell
# myfabric-connect [--log-file LOG_FILE] [--log-level LOG_LEVEL] <moonraker_url> <channel_name> <login> <password>

myfabric-connect ws://localhost:7125/websocket my-printer-id user@example.com my_password
```

**Примечание:** В URL Moonraker используйте `localhost` или IP-адрес сервера Moonraker, вместо `0.0.0.0`, так как `0.0.0.0` не является корректным адресом для подключения клиента.

Дополнительные опции:

- `--log-file`: Указывает путь к файлу логов. По умолчанию: `/var/log/myfabric/myfabric.log`.
  
- `--log-level`: Указывает уровень логирования. Возможные значения: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. По умолчанию: `INFO`.

### Получение версии пакета

```shell
myfabric-connect --version
```

## Поддержание процесса

Чтобы процесс автоматически запускался при старте системы и работал в фоновом режиме, рекомендуется настроить службу systemd.

### Настройка службы systemd (в случае если на 1 хосте подключен 1 принтер)

1. **Создайте файл службы**

   Создайте файл `myfabric.service` в каталоге `/etc/systemd/system/`:

   ```ini
   [Unit]
   Description=MyFabric Connector Service
   After=network.target

   [Service]
   Type=simple
   User=klipper
   EnvironmentFile=/etc/myfabric/myfabric.conf
   ExecStart=/usr/local/bin/myfabric-connect $MOONRAKER_URL $CHANNEL_NAME $LOGIN $PASSWORD --log-file $LOG_FILE --log-level $LOG_LEVEL
   Restart=on-failure
   RestartSec=5s
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

   **Примечания:**

   - Убедитесь, что путь к исполняемому файлу `myfabric-connect` корректен. Вы можете определить путь командой `which myfabric-connect`.
   - Замените `User` на имя пользователя, от которого должен запускаться процесс (например, `klipper`).
   - Использование файла окружения позволяет хранить конфиденциальные данные (например, пароли) отдельно от файла службы.

2. **Создайте файл окружения**

   Создайте файл `/etc/myfabric/myfabric.conf` и добавьте в него следующие строки:

   ```bash
   MOONRAKER_URL=ws://localhost:7125/websocket
   CHANNEL_NAME=my-printer-id
   LOGIN=user@example.com
   PASSWORD=my_password
   LOG_FILE=/var/log/myfabric/myfabric.log
   LOG_LEVEL=INFO
   ```

   **Установите права доступа к файлу:**

   ```bash
   sudo chown root:root /etc/myfabric/myfabric.conf
   sudo chmod 600 /etc/myfabric/myfabric.conf
   ```

3. **Создайте каталог для логов**

   ```bash
   sudo mkdir -p /var/log/myfabric
   sudo chown klipper:klipper /var/log/myfabric
   ```

   Замените `klipper:klipper` на пользователя и группу, от имени которых запускается служба.

4. **Запустите и включите службу**

   ```bash
   # Перезагрузите конфигурацию systemd
   sudo systemctl daemon-reload

   # Включите службу для автоматического запуска при старте системы
   sudo systemctl enable myfabric.service

   # Запустите службу
   sudo systemctl start myfabric.service

   # Проверьте статус службы
   sudo systemctl status myfabric.service
   ```

### Настройка службы systemd (в случае если на 1 хосте подключено более 1 принтера)

1. **Создайте файл службы**

   Создайте файл `myfabric_1.service` в каталоге `/etc/systemd/system/`:

   ```ini
   [Unit]
   Description=MyFabric Connector Service
   After=network.target

   [Service]
   Type=simple
   User=klipper
   EnvironmentFile=/etc/myfabric/myfabric_1.conf
   ExecStart=/usr/local/bin/myfabric-connect $MOONRAKER_URL $CHANNEL_NAME $LOGIN $PASSWORD --log-file $LOG_FILE --log-level $LOG_LEVEL
   Restart=on-failure
   RestartSec=5s
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

   **Примечания:**

   - Убедитесь, что путь к исполняемому файлу `myfabric-connect` корректен. Вы можете определить путь командой `which myfabric-connect`.
   - Замените `User` на имя пользователя, от которого должен запускаться процесс (например, `klipper`).
   - Использование файла окружения позволяет хранить конфиденциальные данные (например, пароли) отдельно от файла службы.

2. **Создайте файл окружения**

   **Обратите внимание, что в случае наличия более одного принтера, подключенного к одноплатнику, меняется только порт подключения**
   Создайте файл `/etc/myfabric/myfabric_1.conf` и добавьте в него следующие строки:

   ```bash
   MOONRAKER_URL=ws://localhost:7125/websocket
   CHANNEL_NAME=my-printer-id
   LOGIN=user@example.com
   PASSWORD=my_password
   LOG_FILE=/var/log/myfabric/myfabric_1.log
   LOG_LEVEL=INFO
   ```

   **Установите права доступа к файлу:**

   ```bash
   sudo chown root:root /etc/myfabric/myfabric_1.conf
   sudo chmod 600 /etc/myfabric/myfabric_1.conf
   ```

3. **Создайте каталог для логов**

   ```bash
   sudo mkdir -p /var/log/myfabric
   sudo chown klipper:klipper /var/log/myfabric
   ```

   Замените `klipper:klipper` на пользователя и группу, от имени которых запускается служба.

4. **Запустите и включите службу**

   ```bash
   # Перезагрузите конфигурацию systemd
   sudo systemctl daemon-reload

   # Включите службу для автоматического запуска при старте системы
   sudo systemctl enable myfabric_1.service

   # Запустите службу
   sudo systemctl start myfabric_1.service

   # Проверьте статус службы
   sudo systemctl status myfabric_1.service
   ```
Для последующего принтера, повторите действия, меняя _1 (порядковый номер) и порт на котором находится экземпляр moonraker (обычно это порты по порядку 7125, 7126 и тд)


## Логирование работы

По умолчанию программа ведет логирование в файл `/var/log/myfabric/myfabric.log`.

- **Просмотр логов в режиме реального времени:**

  ```bash
  tail -f /var/log/myfabric/myfabric.log
  ```

- **Использование `journalctl`:**

  Если вы настроили перенаправление вывода в системный журнал, можете просматривать логи с помощью команды:

  ```bash
  sudo journalctl -u myfabric.service -f
  ```

**Примечание:** Убедитесь, что пользователь, от имени которого запускается служба, имеет права на запись в файл логов.

## Возможные проблемы

### Программа не найдена

```shell
klipper@orangepi3-lts-11-12:~$ myfabric-connect --version
myfabric-connect: command not found
```

**Решение:**

- Убедитесь, что пакет установлен и доступен в `$PATH`.
  
- Проверьте, где находится исполняемый файл:

  ```bash
  which myfabric-connect
  ```

- Если команда не найдена, возможно, необходимо добавить директорию с локальными пакетами Python в переменную окружения `$PATH`:

  ```bash
  export PATH=$PATH:~/.local/bin
  ```

- Или используйте полный путь к исполняемому файлу:

  ```shell
  /home/klipper/.local/bin/myfabric-connect ws://localhost:7125/websocket my-printer-id user@example.com:my_password
  ```

### Проблемы с правами доступа

- **Описание:**
  
  Ошибки, связанные с недостаточными правами доступа к файлам или сетевым портам.

- **Решение:**

  - Убедитесь, что пользователь, от имени которого запускается служба, имеет необходимые права доступа.
  - Проверьте права на файлы конфигурации и логов.
  - Если необходимо, настройте соответствующие разрешения с помощью команд `chown` и `chmod`.

### Ошибки при подключении к Moonraker

- **Описание:**
  
  Программа не может установить соединение с Moonraker.

- **Решение:**

  - Убедитесь, что Moonraker запущен и доступен по указанному адресу и порту.
  - Проверьте правильность указания URL Moonraker в файле конфигурации или при запуске программы.
  - Убедитесь, что нет сетевых ограничений или брандмауэров, блокирующих соединение.

### Ошибки аутентификации в MyFabric

- **Описание:**
  
  В логах появляются сообщения об ошибке аутентификации при подключении к MyFabric.

- **Решение:**

  - Проверьте правильность указанных учетных данных (email и пароль).
  - Убедитесь, что учетная запись активна и имеет доступ к необходимым ресурсам.
  - Попробуйте войти в MyFabric через веб-интерфейс с этими же учетными данными, чтобы убедиться в их корректности.

## Обновление программы

Чтобы обновить программу до последней версии, выполните команду:

```bash
pip install --upgrade myfabric-connector
```

**Проверка текущей версии:**

```bash
myfabric-connect --version
```

## Дополнительная информация

- **Безопасность:**

  - Не храните пароли в открытом виде в файлах или скриптах. Использование файла окружения с ограниченными правами доступа помогает защитить конфиденциальные данные.

- **Настройка логирования:**

  - Вы можете изменить уровень детализации логов, указав параметр `--log-level`. Для отладки используйте уровень `DEBUG`.

- **Остановка службы:**

  ```bash
  sudo systemctl stop myfabric.service
  ```

- **Перезапуск службы:**

  ```bash
  sudo systemctl restart myfabric.service
  ```

- **Просмотр статуса службы:**

  ```bash
  sudo systemctl status myfabric.service
  ```

## Связь с поддержкой

Если у вас возникли вопросы или проблемы с использованием программы, пожалуйста, свяжитесь с поддержкой MyFabric.

---

**Примечание:** Убедитесь, что все команды и пути соответствуют вашей системе и настройкам. При необходимости, адаптируйте инструкции под вашу конкретную среду.
