# myfabric/main.py
import json
import sys
import asyncio
import websockets
import logging
from logging.handlers import RotatingFileHandler
import requests
from pysher import Pusher
import argparse
from .__version__ import __version__
import time
import requests

REVERB_ENDPOINT = "app.myfabric.ru"
APP_KEY = "3ujtmboqehae8ubemo5n"


# Точка входа в программу
def main():
    parser = argparse.ArgumentParser(description='MyFabric Connector')
    parser.add_argument('--version', action='version', version=f'MyFabric Connector {__version__}')
    parser.add_argument('--log-file', default='/var/log/myfabric/myfabric.log', help='Путь к файлу логов')
    parser.add_argument('--log-level', default='INFO',
                        help='Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    parser.add_argument('moonraker_url', help='URL Moonraker WebSocket (например, localhost:7125)')
    parser.add_argument('moonraker_login', help='Логин от moonraker')
    parser.add_argument('moonraker_password', help='Пароль от moonraker')
    parser.add_argument('printer_key', help='Ключ принтера в MyFabric (хэш-строка)')
    parser.add_argument('myfabric_login', help='E-mail от учетной записи MyFabric')
    parser.add_argument('myfabric_password', help='Пароль от учётной записи MyFabric')
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
        asyncio.run(start_proxy(args.moonraker_url, args.printer_key, args.myfabric_login, args.myfabric_password,
                                args.moonraker_login,
                                args.moonraker_password))
    except KeyboardInterrupt:
        logger.info("Остановка программы по запросу пользователя")
    except Exception as e:
        logger.exception(f"Произошла ошибка: {e}")
        sys.exit(1)


# Функция для запуска прокси
async def start_proxy(moonraker_url, printer_key, login, password, moonraker_login, moonraker_password):
    channel_name = f'private-printers.{printer_key}'
    bearer = login_fabric(login, password)

    moonraker_api_key = get_moonraker_token(moonraker_url, moonraker_login, moonraker_password)
    moonraker_ws = f"ws://{moonraker_url}/websocket?token={moonraker_api_key}"

    await proxy_moonraker_reverb(moonraker_ws, channel_name, printer_key, bearer)


def login_fabric(login, password):
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
    return bearer


def auth_reverb(bearer, channel_name, socket_id):
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


def get_moonraker_token(moonraker_url, username, password):
    response = requests.post(f"http://{moonraker_url}/access/login", json={
        'username': username,
        'password': password,
        "source": "moonraker"
    })
    if response.status_code != 200:
        raise Exception(f"Failed to obtain Moonraker token: {response.status_code} {response.text}")
    data = response.json()
    bearer = data['result']['token']
    response = requests.get(f"http://{moonraker_url}/access/oneshot_token", headers={
        "Authorization": f'Bearer {bearer}'
    })
    data = response.json()
    return data.get("result")


def get_moonraker_subscribe_message() -> str:
    body = {"jsonrpc": "2.0", "method": "printer.objects.subscribe", "params": {
        "objects": {"webhooks": None, "configfile": None, "mcu": None, "mcu U_1": None, "output_pin sound": None,
                    "gcode_move": None, "bed_mesh": None, "chamber_fan chamber_fan": None,
                    "controller_fan board_fan": None, "display_status": None, "exclude_object": None, "extruder": None,
                    "fan_generic auxiliary_cooling_fan": None, "fan_generic chamber_circulation_fan": None,
                    "fan_generic cooling_fan": None, "filament_switch_sensor fila": None,
                    "hall_filament_width_sensor": None, "heater_bed": None, "heater_fan hotend_fan": None,
                    "heater_fan hotend_fan2": None, "heater_generic chamber": None, "heaters": None,
                    "idle_timeout": None, "manual_probe": None, "motion_report": None, "output_pin beeper": None,
                    "output_pin caselight": None, "output_pin ctlyd": None, "pause_resume": None, "print_stats": None,
                    "probe": None, "query_endstops": None, "save_variables": None, "system_stats": None,
                    "tmc2209 extruder": None, "tmc2209 stepper_z": None, "tmc2209 stepper_z1": None,
                    "tmc2240 stepper_x": None, "tmc2240 stepper_y": None, "toolhead": None, "virtual_sdcard": None,
                    "z_tilt": None}}, "id": round(time.time())}

    msg = json.dumps(body)
    return msg


async def proxy_moonraker_reverb(moonraker_url, channel_name, printer_key, bearer):
    logger = logging.getLogger('myfabric')

    loop = asyncio.get_event_loop()  # Получаем ссылку на главный цикл событий

    # Initialize queues
    moonraker_to_reverb_queue = asyncio.Queue()
    reverb_to_moonraker_queue = asyncio.Queue()

    # Connect to Moonraker
    async with websockets.connect(moonraker_url) as moonraker_ws:
        logger.info(f"Connected to Moonraker at {moonraker_url}")

        # Initialize Pusher client
        reverb_pusher = Pusher(
            custom_host=REVERB_ENDPOINT,
            key=APP_KEY,
            secure=True,
            daemon=True,
            reconnect_interval=5
        )

        def re_subscribe():
            try:
                ws_auth_token = auth_reverb(bearer, channel_name, reverb_pusher.connection.socket_id)
                channel = reverb_pusher.subscribe(channel_name, ws_auth_token)
                channel.bind('moonraker-request', reverb_message_handler)
                reverb_pusher.channel = channel
                logger.info("Successfully re-subscribed to Reverb channel.")
            except Exception as e:
                logger.error(f"Failed to re-subscribe: {e}")

        # Connection handlers
        async def moonraker_reader():
            async for message in moonraker_ws:
                logger.debug(f"Received from Moonraker: {message}")
                await moonraker_to_reverb_queue.put(message)

        async def moonraker_writer():
            logger.debug(f"moonraker_writer INIT")
            while True:
                message = await reverb_to_moonraker_queue.get()
                logger.debug(f"Trying to send to Moonraker: {message}")
                await moonraker_ws.send(message)
                logger.debug(f"Sent to Moonraker: {message}")

        def reverb_connect_handler(data):
            logger.info("Connected to Reverb")
            re_subscribe()

        def reverb_message_handler(message):
            logger.debug(f"Received from Reverb: {message}")
            asyncio.run_coroutine_threadsafe(
                reverb_to_moonraker_queue.put(message),
                loop
            )

        def reverb_connection_disconnected_handler(data):
            logger.warning("Reverb connection disconnected. Attempting to reconnect...")

        def reverb_connection_recovered_handler(data):
            logger.info("Reverb connection recovered.")
            re_subscribe()

        # Bind handlers and connect
        reverb_pusher.connection.bind('pusher:connection_established', reverb_connect_handler)
        reverb_pusher.connection.bind('pusher:connection_disconnected', reverb_connection_disconnected_handler)
        reverb_pusher.connection.bind('pusher:connection_recovered', reverb_connection_recovered_handler)
        reverb_pusher.connect()

        # Start coroutines
        await asyncio.gather(
            moonraker_reader(),
            moonraker_writer(),
            handle_moonraker_to_reverb(moonraker_to_reverb_queue, reverb_pusher, channel_name, printer_key,
                                       moonraker_ws)
        )


def standardize_message(message: str) -> dict:
    logger = logging.getLogger('myfabric')
    try:
        msg = json.loads(message)
        standardized = {}
        # Определяем тип события
        if 'method' in msg:
            method = msg['method']
            if method == 'notify_status_update':
                standardized['event_type'] = 'status_update'
                standardized['timestamp'] = time.time()
                # Извлекаем данные статуса
                standardized['data'] = msg['params'][0]
            elif method == 'notify_proc_stat_update':
                standardized['event_type'] = 'proc_stat_update'
                standardized['timestamp'] = time.time()
                standardized['data'] = msg['params'][0]
            else:
                # Обработка других методов notify_*
                standardized['event_type'] = method
                standardized['timestamp'] = time.time()
                standardized['data'] = msg.get('params', [])
        elif 'result' in msg:
            standardized['event_type'] = 'initial_status'
            standardized['timestamp'] = time.time()
            standardized['data'] = msg['result']['status']
        else:
            # Другие типы сообщений
            standardized['event_type'] = 'unknown'
            standardized['timestamp'] = time.time()
            standardized['data'] = msg
        return standardized
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON message: {e}")
        return {}


async def handle_moonraker_to_reverb(queue, reverb_pusher, channel_name, printer_key, moonraker_ws):
    logger = logging.getLogger('myfabric')
    subscribed = False
    message_buffer = []
    buffer_lock = asyncio.Lock()

    async def buffer_messages():
        while True:
            await asyncio.sleep(10)  # Ждем 10 секунд
            async with buffer_lock:
                if message_buffer:
                    # Отправляем накопленные сообщения
                    combined_message = {
                        "messages": message_buffer,
                        "timestamp": time.time()
                    }
                    if channel_name in reverb_pusher.channels:
                        reverb_pusher.channels[channel_name].trigger('client-event', json.dumps({"health-check": True}))
                        # reverb_pusher.channels[channel_name].trigger('client-event', json.dumps(combined_message))
                        res = requests.post(f"https://{REVERB_ENDPOINT}/api/webhooks/printers/{printer_key}/notify",
                                            data=json.dumps(combined_message),
                                            headers={'Content-Type': 'application/json'})
                        logger.debug(f"Sent combined message to Reverb: {res.status_code}")
                    else:
                        logger.debug("No channel found for Reverb")
                    # Очищаем буфер
                    message_buffer.clear()

    # Запускаем задачу для отправки сообщений из буфера и сохраняем ссылку на неё
    buffer_task = asyncio.create_task(buffer_messages())

    while True:
        message = await queue.get()
        if not subscribed:
            await moonraker_ws.send(get_moonraker_subscribe_message())
            subscribed = True
            logger.debug("Subscribed to Moonraker updates")

        standardized_message = standardize_message(message)
        if standardized_message:
            async with buffer_lock:
                message_buffer.append(standardized_message)
            logger.debug(f"Buffered message: {standardized_message}")
        else:
            logger.error("Failed to standardize message")


if __name__ == '__main__':
    main()
