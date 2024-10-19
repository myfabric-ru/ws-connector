# myfabric/main.py

import asyncio
import websockets
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myfabric')


async def proxy(local_url, remote_url):
    delay = 1  # Начальная задержка переподключения в секундах
    max_delay = 60  # Максимальная задержка переподключения в секундах
    while True:
        try:
            async with websockets.connect(local_url) as local_ws, websockets.connect(remote_url) as remote_ws:
                logger.info("Установлено соединение с локальным и удаленным вебсокетами")
                delay = 1  # Сброс задержки при успешном подключении
                await asyncio.gather(
                    forward_messages(local_ws, remote_ws, 'local_to_remote'),
                    forward_messages(remote_ws, local_ws, 'remote_to_local'),
                    keep_alive(local_ws, 'local'),
                    keep_alive(remote_ws, 'remote'),
                )
        except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.InvalidStatusCode,
                ConnectionRefusedError) as e:
            logger.warning(f"Соединение прервано: {e}. Переподключение через {delay} секунд...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)  # Увеличиваем задержку до максимума
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка: {e}", exc_info=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
        else:
            logger.info("Соединение закрыто нормально")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
        finally:
            logger.info("Попытка переподключения...")


async def forward_messages(ws_from, ws_to, direction):
    try:
        async for message in ws_from:
            logger.debug(f"Пересылка сообщения ({direction}): {message}")
            await ws_to.send(message)
    except Exception as e:
        logger.warning(f"Ошибка при пересылке сообщений ({direction}): {e}")


async def keep_alive(ws, name):
    try:
        while True:
            await ws.ping()
            logger.debug(f"Отправлен пинг на {name} вебсокет")
            await asyncio.sleep(30)  # Отправляем пинг каждые 30 секунд
    except Exception as e:
        logger.warning(f"Потеряно соединение с {name} вебсокетом: {e}")


def start():
    if len(sys.argv) != 4 or sys.argv[1] != 'start':
        print("Использование: myfabric start <local_url> <remote_url>")
        sys.exit(1)
    local_url = sys.argv[2]
    remote_url = sys.argv[3]
    try:
        asyncio.run(proxy(local_url, remote_url))
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)


if __name__ == '__main__':
    start()
