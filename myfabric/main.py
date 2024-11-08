# -*- coding: utf-8 -*-
import json
import sys
import websocket
import threading
import logging
from logging.handlers import RotatingFileHandler
from pysher_khonik import Pusher
import argparse
from .__version__ import __version__
import time
import requests
from .install_runner import run_install, run_uninstall

try:
    import queue  # Python 3
except ImportError:
    import Queue as queue  # Python 2

REVERB_ENDPOINT = "app.myfabric.ru"
APP_KEY = "3ujtmboqehae8ubemo5n"


def main():
    parser = argparse.ArgumentParser(description='MyFabric Connector')
    parser.add_argument('--version', action='version', version='MyFabric Connector {}'.format(__version__))
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # Подкоманда start
    start_parser = subparsers.add_parser('start', help='Запуск подключения к Moonraker')
    start_parser.add_argument('--log-file', default='/var/log/myfabric/myfabric.log', help='Путь к файлу логов')
    start_parser.add_argument('--log-level', default='INFO', help='Уровень логирования')
    start_parser.add_argument('moonraker_url', help='URL Moonraker WebSocket')
    start_parser.add_argument('printer_key', help='Ключ принтера в MyFabric')
    start_parser.add_argument('myfabric_login', help='E-mail от учетной записи MyFabric')
    start_parser.add_argument('myfabric_password', help='Пароль от учётной записи MyFabric')

    # Подкоманда install/uninstall
    subparsers.add_parser('install', help='Установка необходимых компонентов')
    uninstall_parser = subparsers.add_parser('uninstall', help='Удаление службы')
    uninstall_parser.add_argument('printer_key', help='Ключ принтера в MyFabric')

    args = parser.parse_args()
    if args.command == "start":
        start_program(args)
    elif args.command == "install":
        run_install()
    elif args.command == "uninstall":
        run_uninstall(args.printer_key)
    else:
        parser.print_help()


def start_program(args):
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = logging.getLogger('myfabric')
    logger.setLevel(log_level)

    handler = RotatingFileHandler(args.log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    try:
        start_proxy(args.moonraker_url, args.printer_key, args.myfabric_login, args.myfabric_password)
    except KeyboardInterrupt:
        logger.info("Остановка программы по запросу пользователя")
    except Exception as e:
        logger.exception("Произошла ошибка: {}".format(e))
        sys.exit(1)


def start_proxy(moonraker_url, printer_key, login, password):
    logger = logging.getLogger('myfabric')
    channel_name = 'private-printers.{}'.format(printer_key)
    bearer = login_fabric(login, password)
    moonraker_ws_url = "ws://{}/websocket?token={}".format(moonraker_url, get_moonraker_token(moonraker_url))

    moonraker_to_reverb_queue = queue.Queue()
    reverb_to_moonraker_queue = queue.Queue()

    # Запуск WebSocket клиента
    ws = websocket.WebSocketApp(
        moonraker_ws_url,
        on_message=lambda ws, message: on_moonraker_message(ws, message, moonraker_to_reverb_queue),
        on_error=on_moonraker_error,
        on_close=on_moonraker_close
    )

    moonraker_thread = threading.Thread(target=ws.run_forever, name="MoonrakerWebSocketThread")
    moonraker_thread.daemon = True  # Устанавливаем daemon отдельно для совместимости с Python 2
    moonraker_thread.start()

    reverb_pusher = Pusher(custom_host=REVERB_ENDPOINT, key=APP_KEY, secure=True, daemon=True, reconnect_interval=5,
                           log_level=logging.DEBUG)

    # Обработчики подключения Reverb
    def handle_connection_established():
        reverb_connect_handler(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue)

    def handle_connection_recovered():
        reverb_connection_recovered_handler(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue)

    def reverb_connection_disconnected_handler(data):
        logger = logging.getLogger('myfabric')
        logger.warning("Reverb connection disconnected. Attempting to reconnect...")

    # Обработчики подключения Reverb
    reverb_pusher.connection.bind('pusher:connection_established', handle_connection_established)
    reverb_pusher.connection.bind('pusher:connection_disconnected', reverb_connection_disconnected_handler)
    reverb_pusher.connection.bind('pusher:connection_recovered', handle_connection_recovered)

    def start_reverb_connection():
        logger.info("Starting Reverb WebSocket")
        reverb_pusher.connection.run()
        logger.info("Reverb WebSocket connection closed")

    # Запуск Reverb WebSocket в отдельном потоке
    reverb_thread = threading.Thread(target=start_reverb_connection, name="ReverbWebSocketThread")
    reverb_thread.daemon = True
    reverb_thread.start()

    # Ожидание успешного подключения Reverb
    while reverb_pusher.connection.state != 'connected':
        logger.info("Waiting for Reverb connection... Current state: {}".format(reverb_pusher.connection.state))
        time.sleep(5)

    logger.info("Reverb connected: {}".format(reverb_pusher.connection.state))

    # Запуск потоков для обработки сообщений
    threading.Thread(target=handle_moonraker_to_reverb, args=(ws, moonraker_to_reverb_queue, printer_key, bearer),
                     name="MoonrakerToReverbThread").start()
    threading.Thread(target=handle_reverb_to_moonraker, args=(reverb_to_moonraker_queue, ws),
                     name="ReverbToMoonrakerThread").start()


def on_moonraker_message(ws, message, moonraker_to_reverb_queue):
    logger = logging.getLogger('myfabric')
    logger.debug("Received from Moonraker: {}".format(message))
    moonraker_to_reverb_queue.put(standardize_message(message))


def on_moonraker_error(ws, error):
    logger = logging.getLogger('myfabric')
    logger.error("Moonraker WebSocket error: {}".format(error))


def on_moonraker_close(ws):
    logger = logging.getLogger('myfabric')
    logger.info("Moonraker WebSocket closed")


def re_subscribe(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue):
    logger = logging.getLogger('myfabric')
    try:
        if not reverb_pusher.connection.socket_id:
            logger.error("No socket id in connection: {}".format(reverb_pusher.connection))
            return
        ws_auth_token = auth_reverb(bearer, channel_name, reverb_pusher.connection.socket_id)
        channel = reverb_pusher.subscribe(channel_name, ws_auth_token)
        channel.bind('moonraker-request', lambda message: on_reverb_message(message, reverb_to_moonraker_queue))
    except Exception as e:
        logger.error("Failed to re-subscribe: {}".format(e))


def reverb_connect_handler(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue):
    logger = logging.getLogger('myfabric')
    logger.info("Connected to Reverb")
    logger.info("Connection state: {}".format(reverb_pusher.connection.state))
    re_subscribe(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue)


def reverb_connection_recovered_handler(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue):
    logger = logging.getLogger('myfabric')
    logger.info("Reverb connection recovered.")
    re_subscribe(reverb_pusher, channel_name, bearer, reverb_to_moonraker_queue)


def on_reverb_message(message, reverb_to_moonraker_queue):
    """Обработчик сообщений Reverb, добавляющий их в очередь для отправки на Moonraker"""
    logger = logging.getLogger('myfabric')
    logger.debug("Received from Reverb: {}".format(message))
    reverb_to_moonraker_queue.put(message)


def handle_moonraker_to_reverb(ws, moonraker_queue, printer_key, bearer):
    logger = logging.getLogger('myfabric')
    message_buffer = []
    subscribed = False
    while True:
        message = moonraker_queue.get()
        if not subscribed:
            ws.send(get_moonraker_subscribe_message())
            subscribed = True
            logger.debug("Subscribed to Moonraker updates")

        if message:
            message_buffer.append(message)
            if len(message_buffer) >= 10:
                combined_message = {"messages": message_buffer, "timestamp": time.time()}
                headers = {'Authorization': 'Bearer {}'.format(bearer), 'Content-Type': 'application/json'}
                res = requests.post("https://{}/api/webhooks/printers/{}/notify".format(REVERB_ENDPOINT, printer_key),
                                    json=combined_message, headers=headers)
                logger.debug("Sent combined message to Reverb: {}".format(res.status_code))
                message_buffer.clear()


def handle_reverb_to_moonraker(reverb_queue, ws):
    while True:
        message = reverb_queue.get()
        if message:
            logger = logging.getLogger('myfabric')
            logger.debug("Sending to Moonraker: {}".format(message))
            ws.send(message)


def login_fabric(login, password):
    response = requests.post('https://{}/api/auth/login'.format(REVERB_ENDPOINT),
                             json={'email': login, 'password': password})
    data = response.json()
    return data['access_token'] if response.status_code == 200 else None


def auth_reverb(bearer, channel_name, socket_id):
    logger = logging.getLogger('myfabric')
    logger.info("bearer: {}".format(bearer))
    logger.info("channel_name: {}".format(channel_name))
    logger.info("socket_id: {}".format(socket_id))
    url = "https://{}/api/broadcasting/auth".format(REVERB_ENDPOINT)
    logger.info("url: {}".format(url))
    response = requests.post(url,
                             json={"channel_name": channel_name, "socket_id": socket_id},
                             headers={'Authorization': 'Bearer {}'.format(bearer)})

    logger.info("Auth response: {}".format(response.text))
    return response.json().get("auth")


def get_moonraker_token(moonraker_url):
    response = requests.get("http://{}/access/oneshot_token".format(moonraker_url))
    return response.json().get("result")


def get_moonraker_subscribe_message():
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
    return json.dumps(body)


def standardize_message(message):
    logger = logging.getLogger('myfabric')
    try:
        msg = json.loads(message)
        standardized = {}
        if 'method' in msg:
            method = msg['method']
            if method == 'notify_status_update':
                standardized['event_type'] = 'status_update'
                standardized['timestamp'] = time.time()
                standardized['data'] = msg['params'][0]
            elif method == 'notify_proc_stat_update':
                standardized['event_type'] = 'proc_stat_update'
                standardized['timestamp'] = time.time()
                standardized['data'] = msg['params'][0]
            else:
                standardized['event_type'] = method
                standardized['timestamp'] = time.time()
                standardized['data'] = msg.get('params', [])
        elif 'result' in msg:
            standardized['event_type'] = 'initial_status'
            standardized['timestamp'] = time.time()
            standardized['data'] = msg['result']['status']
        else:
            standardized['event_type'] = 'unknown'
            standardized['timestamp'] = time.time()
            standardized['data'] = msg
        return standardized
    except ValueError as e:
        logger.error("Failed to decode JSON message: {}".format(e))
        return {}


if __name__ == '__main__':
    main()
