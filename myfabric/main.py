# myfabric/main.py

import asyncio
import websockets
import sys

async def proxy(local_url, remote_url):
    async with websockets.connect(local_url) as local_ws, websockets.connect(remote_url) as remote_ws:
        async def forward(ws_from, ws_to):
            async for message in ws_from:
                await ws_to.send(message)
        await asyncio.gather(
            forward(local_ws, remote_ws),
            forward(remote_ws, local_ws),
        )

def start():
    if len(sys.argv) != 4 or sys.argv[1] != 'start':
        print("Использование: myfabric start <printer_url> <remote_url>")
        sys.exit(1)
    local_url = sys.argv[2]
    remote_url = sys.argv[3]
    asyncio.run(proxy(local_url, remote_url))

if __name__ == '__main__':
    start()
