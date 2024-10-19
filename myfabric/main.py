# myfabric/main.py

import sys
import asyncio
import websockets
import logging
import threading
import time
import pusherclient

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myfabric')

# Константы
CLIENT_ID = '347189'  # Замените на ваш CLIENT_ID, если требуется
CLIENT_SECRET = '3ujtmboqehae8ubemo5n'  # Замените на ваш CLIENT_SECRET, если требуется
REVERB_ENDPOINT = 'ws://127.0.0.1'  # Замените на ваш эндпоинт Reverb
REVERB_PORT = 9000  # Замените на ваш эндпоинт Reverb
APP_KEY = 'rx2qs9ivfr2uioolb2w2'  # Замените на ваш APP_KEY для Pusher


# Функция для запуска прокси
def start_proxy(moonraker_url, channel_name):
    # Создаем asyncio loop для работы в отдельном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Запускаем задачи
    tasks = [
        moonraker_to_reverb(loop, moonraker_url, channel_name),
        reverb_to_moonraker(loop, moonraker_url, channel_name)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))


# Пересылка сообщений из Moonraker в Reverb
async def moonraker_to_reverb(loop, moonraker_url, channel_name):
    async with websockets.connect(moonraker_url) as moonraker_ws:
        logger.info(f"Подключено к Moonraker на {moonraker_url}")

        # Инициализируем Pusher-клиент
        reverb_pusher = pusherclient.Pusher(
            key=APP_KEY,
            cluster='mt1',
            secure=False,
            ws_host=REVERB_ENDPOINT,  # Замените на ваш хост Reverb
            ws_port=REVERB_PORT,  # Замените на ваш порт Reverb
            daemon=True,
            reconnect_interval=5
        )

        # Функция обратного вызова при установлении соединения
        def connect_handler(data):
            logger.info("Соединение с Reverb установлено (Moonraker to Reverb)")
            # Подписка на канал не требуется для отправки сообщений

        reverb_pusher.connection.bind('pusher:connection_established', connect_handler)
        reverb_pusher.connect()

        # Ждем установления соединения
        while not reverb_pusher.connection.connected:
            await asyncio.sleep(0.1)

        while True:
            try:
                message = await moonraker_ws.recv()
                logger.debug(f"Получено сообщение от Moonraker: {message}")

                # Отправляем сообщение в публичный канал Reverb
                channel = reverb_pusher[channel_name]
                channel.trigger('client-event', message)
            except websockets.ConnectionClosed:
                logger.warning("Соединение с Moonraker закрыто")
                break
            except Exception as e:
                logger.error(f"Ошибка при пересылке сообщения в Reverb: {e}")


# Пересылка сообщений из Reverb в Moonraker
async def reverb_to_moonraker(loop, moonraker_url, channel_name):
    async with websockets.connect(moonraker_url) as moonraker_ws:
        logger.info(f"Подключено к Moonraker на {moonraker_url}")

        # Инициализируем Pusher-клиент
        reverb_pusher = pusherclient.Pusher(
            key=APP_KEY,
            cluster='mt1',
            secure=False,
            ws_host=REVERB_ENDPOINT,  # Замените на ваш хост Reverb
            ws_port=REVERB_PORT,  # Замените на ваш порт Reverb
            daemon=True,
            reconnect_interval=5
        )

        # Функция обратного вызова при установлении соединения
        def connect_handler(data):
            logger.info("Соединение с Reverb установлено (Reverb to Moonraker)")
            # Подписываемся на публичный канал
            channel = reverb_pusher.subscribe(channel_name)
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
        while not reverb_pusher.connection.connected:
            await asyncio.sleep(0.1)

        # Поддерживаем соединение
        while True:
            await asyncio.sleep(1)


# Точка входа в программу
def main():
    if len(sys.argv) != 3:
        print("Использование: myfabric-connect <moonraker_url> <channel_name>")
        sys.exit(1)

    moonraker_url = sys.argv[1]
    channel_name = sys.argv[2]

    # Запускаем прокси в отдельном потоке
    proxy_thread = threading.Thread(target=start_proxy, args=(moonraker_url, channel_name))
    proxy_thread.start()

    # Поддерживаем основной поток активным
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
