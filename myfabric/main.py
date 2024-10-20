# myfabric/main.py
import json
import sys
import asyncio
import websockets
import logging
import threading
import time
import requests
from pysher import Pusher

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myfabric')

# Константы
CLIENT_ID = '347189'  # Замените на ваш CLIENT_ID, если требуется
CLIENT_SECRET = ''  # Замените на ваш CLIENT_SECRET, если требуется
REVERB_ENDPOINT = 'app.myfabric.ru'  # Замените на ваш эндпоинт Reverb
REVERB_PORT = 443  # Замените на ваш эндпоинт Reverb
APP_KEY = '3ujtmboqehae8ubemo5n'  # Замените на ваш APP_KEY для Pusher


# Функция для запуска прокси
def start_proxy(moonraker_url, channel_name, login, password):
    res = requests.post(f'https://{REVERB_ENDPOINT}/api/auth/login', json={
        'email': login,
        'password': password,
    })
    if res.status_code != 200:
        logger.error(f'CANNOT SIGN IN ({res.status_code}): {res.text}')
    data = res.json()
    logger.info(f'LOGGED IN ({res.status_code}):')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Запускаем задачи
    tasks = [
        moonraker_to_reverb(loop, moonraker_url, channel_name, data['access_token']),
        reverb_to_moonraker(loop, moonraker_url, channel_name, data['access_token'])
    ]
    loop.run_until_complete(asyncio.gather(*tasks))


# Пересылка сообщений из Moonraker в Reverb
async def moonraker_to_reverb(loop, moonraker_url, channel_name, bearer):
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
                logger.error(f"Ошибка при пересылке сообщения в Reverb: {e} ({json.dumps(message)})")


# Пересылка сообщений из Reverb в Moonraker
async def reverb_to_moonraker(loop, moonraker_url, channel_name, bearer):
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
            # Подписываемся на публичный канал
            ws_auth_token = auth_ws(bearer, channel_name, reverb_pusher.connection.socket_id)
            channel = reverb_pusher.subscribe(channel_name, ws_auth_token)
            channel.bind('client-event', reverb_message_handler)

        # Обработчик сообщений из Reverb
        def reverb_message_handler(message):
            logger.debug(f"Получено сообщение от Reverb: {message}")
            asyncio.run_coroutine_threadsafe(
                moonraker_ws.send(message),
                loop
            )

        reverb_pusher.connection.bind('pusher:connection_established', connect_handler)
        reverb_pusher.connect()

        # Ждем установления соединения
        while reverb_pusher.connection.state != "connected":
            await asyncio.sleep(0.1)

        # Поддерживаем соединение
        while True:
            await asyncio.sleep(1)


def auth_ws(bearer, channel_name, socket_id):
    request_data = {
        "channel_name": channel_name,
        "socket_id": socket_id
    }
    response = requests.post(
        f"https://{REVERB_ENDPOINT}/api/broadcasting/auth",
        json=request_data,
        headers={
            'Authorization': f'Bearer {bearer}'  # Получите токен через аутентификацию
        }
    )
    assert response.status_code == 200, f"Failed to get auth token from my fabric"
    auth_key = response.json()["auth"]
    return auth_key


# Точка входа в программу
def main():
    if len(sys.argv) < 3:
        print("Использование: myfabric-connect <moonraker_url> <channel_name> <login>:<password>")
        sys.exit(1)

    moonraker_url = sys.argv[1]
    channel_name = sys.argv[2]

    if len(sys.argv) < 3:
        print("Введите логин")
        login = input("Login: ")
        print("Введите пароль")
        password = input("Password: ")
    else:
        creds = sys.argv[3]
        [login, password] = creds.split(":")

    # Запускаем прокси в отдельном потоке
    proxy_thread = threading.Thread(target=start_proxy, args=(moonraker_url, channel_name, login, password))
    proxy_thread.start()

    # Поддерживаем основной поток активным
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
