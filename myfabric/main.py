# myfabric/main.py

import sys
import asyncio
import websockets
import logging
from logging.handlers import RotatingFileHandler
import requests
from pysher import Pusher
import argparse
from .__version__ import __version__

REVERB_ENDPOINT = "app.myfabric.ru"
APP_KEY = "3ujtmboqehae8ubemo5n"


# Точка входа в программу
def main():
    parser = argparse.ArgumentParser(description='MyFabric Connector')
    parser.add_argument('--version', action='version', version=f'MyFabric Connector {__version__}')
    parser.add_argument('--log-file', default='/var/log/myfabric/myfabric.log', help='Путь к файлу логов')
    parser.add_argument('--log-level', default='INFO',
                        help='Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    parser.add_argument('moonraker_url', help='URL Moonraker WebSocket (например, ws://localhost:7125/websocket)')
    parser.add_argument('printer_key', help='Ключ принтера в MyFabric (хэш-строка)')
    parser.add_argument('login', help='E-mail от учетной записи MyFabric')
    parser.add_argument('password', help='Пароль от учётной записи MyFabric')

    args = parser.parse_args()

    # Настройка логирования
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = logging.getLogger('myfabric')
    logger.setLevel(log_level)

    # Создаем обработчик логов с ротацией
    handler = RotatingFileHandler(
        args.log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Запуск основного цикла
    try:
        asyncio.run(start_proxy(args.moonraker_url, f'private-printers.{args.printer_key}', args.login, args.password))
    except KeyboardInterrupt:
        logger.info("Остановка программы по запросу пользователя")
    except Exception as e:
        logger.exception(f"Произошла ошибка: {e}")
        sys.exit(1)


# Функция для запуска прокси
async def start_proxy(moonraker_url, channel_name, login, password):
    logger = logging.getLogger('myfabric')

    # Аутентификация
    res = requests.post(f'https://{REVERB_ENDPOINT}/api/auth/login', json={
        'email': login,
        'password': password,
    })
    if res.status_code != 200:
        logger.error(f'CANNOT SIGN IN ({res.status_code}): {res.text}')
        return
    data = res.json()
    logger.info(f'LOGGED IN ({res.status_code})')

    bearer = data['access_token']

    # Запуск задач
    await asyncio.gather(
        moonraker_to_reverb(moonraker_url, channel_name, bearer),
        reverb_to_moonraker(moonraker_url, channel_name, bearer)
    )


# Пересылка сообщений из Moonraker в Reverb
async def moonraker_to_reverb(moonraker_url, channel_name, bearer):
    logger = logging.getLogger('myfabric')
    try:
        async with websockets.connect(moonraker_url) as moonraker_ws:
            logger.info(f"Подключено к Moonraker на {moonraker_url}")
            # Инициализируем Pusher-клиент
            reverb_pusher = Pusher(
                custom_host=REVERB_ENDPOINT,
                key=APP_KEY,
                secure=True,
                daemon=True,
                reconnect_interval=5
            )

            # Функция обратного вызова при установлении соединения
            def connect_handler(data):
                logger.info("Соединение с Reverb установлено (Moonraker to Reverb)")
                # Аутентифицируемся и подписываемся на приватный канал
                ws_auth_token = auth_ws(bearer, channel_name, reverb_pusher.connection.socket_id)
                channel = reverb_pusher.subscribe(channel_name, ws_auth_token)
                # Сохраняем объект канала для отправки сообщений
                reverb_pusher.channel = channel

            reverb_pusher.connection.bind('pusher:connection_established', connect_handler)
            reverb_pusher.connect()

            # Ждем установления соединения и подписки на канал
            while reverb_pusher.connection.state != "connected" or channel_name not in reverb_pusher.channels:
                await asyncio.sleep(0.1)

            while True:
                try:
                    message = await moonraker_ws.recv()
                    logger.debug(f"Получено сообщение от Moonraker: {message}")
                    # Отправляем сообщение в приватный канал Reverb
                    reverb_pusher.channel.trigger('client-event', message)
                except websockets.ConnectionClosed:
                    logger.warning("Соединение с Moonraker закрыто")
                    break
                except Exception as e:
                    logger.error(f"Ошибка при пересылке сообщения в Reverb: {e}")
    except Exception as e:
        logger.exception(f"Ошибка в moonraker_to_reverb: {e}")


# Пересылка сообщений из Reverb в Moonraker
async def reverb_to_moonraker(moonraker_url, channel_name, bearer):
    logger = logging.getLogger('myfabric')
    try:
        async with websockets.connect(moonraker_url) as moonraker_ws:
            logger.info(f"Подключено к Moonraker на {moonraker_url}")

            # Инициализируем Pusher-клиент
            reverb_pusher = Pusher(
                custom_host=REVERB_ENDPOINT,
                key=APP_KEY,
                secure=True,
                daemon=True,
                reconnect_interval=5,
            )

            # Функция обратного вызова при установлении соединения
            def connect_handler(data):
                logger.info("Соединение с Reverb установлено (Reverb to Moonraker)")
                # Подписываемся на приватный канал
                ws_auth_token = auth_ws(bearer, channel_name, reverb_pusher.connection.socket_id)
                channel = reverb_pusher.subscribe(channel_name, ws_auth_token)
                channel.bind('moonraker-request', reverb_message_handler)

            # Обработчик сообщений из Reverb
            def reverb_message_handler(message):
                logger.debug(f"Получено сообщение от Reverb: {message}")
                asyncio.run_coroutine_threadsafe(
                    moonraker_ws.send(message),
                    asyncio.get_event_loop()
                )

            reverb_pusher.connection.bind('pusher:connection_established', connect_handler)
            reverb_pusher.connect()

            # Ждем установления соединения
            while reverb_pusher.connection.state != "connected":
                await asyncio.sleep(0.1)

            # Поддерживаем соединение
            while True:
                await asyncio.sleep(1)
    except Exception as e:
        logger.exception(f"Ошибка в reverb_to_moonraker: {e}")


def auth_ws(bearer, channel_name, socket_id):
    logger = logging.getLogger('myfabric')
    request_data = {
        "channel_name": channel_name,
        "socket_id": socket_id
    }
    response = requests.post(
        f"https://{REVERB_ENDPOINT}/api/broadcasting/auth",
        json=request_data,
        headers={
            'Authorization': f'Bearer {bearer}'
        }
    )
    if response.status_code != 200:
        logger.error(f"Failed to get auth token from MyFabric ({response.status_code}): {response.text}")
        raise Exception("Authentication failed")
    auth_key = response.json().get("auth")
    if not auth_key:
        logger.error("Auth key not found in response")
        raise Exception("Authentication failed")
    return auth_key


if __name__ == '__main__':
    main()
