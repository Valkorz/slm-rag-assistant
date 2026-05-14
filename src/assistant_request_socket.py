import asyncio
import json
from typing import Callable, Optional
from aiohttp import web
import aiohttp_cors

class AssistantRequestSocket:
    #The user may use the functionalities of this application through HTTP requests.

    # Public
    connection_open: bool = False
    host: str
    port: int

    # Private
    _tcp_callback: Optional[Callable[[str], str]] = None
    _app: Optional[web.Application] = None
    _runner: Optional[web.AppRunner] = None
    _site: Optional[web.TCPSite] = None
    _event_loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(self, host: str = "127.0.0.1", port: int = 8008):
        self.host = host
        self.port = port
        self._app = None
        self._runner = None
        self._site = None
        self._event_loop = None

    def parse_response(self, response: str) -> dict[str, str]:
        try:
            return json.loads(response)
        except Exception:
            try:
                data = "{" + response.split("{", 1)[1]
                return json.loads(data)
            except Exception as e:
                print(f"Error while parsing response: {str(e)}")
                return {}
        
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._event_loop = loop

    def sethost(self, host: str):
        self.host = host

    def setport(self, port: int):
        self.port = port

    def set_callback_fn(self, callback: Optional[Callable[[str], str]]):
        self._tcp_callback = callback

    async def _handle_request(self, request: web.Request) -> web.StreamResponse:
        stream = web.StreamResponse(
            status=200,
            headers={'Content-Type': 'application/json'},
        )
        try:
            payload = await request.text()
            addr = request.remote
            print(f"HTTP request from {addr}: {payload}")

            await stream.prepare(request)

            body = '{"error": "No callback registered."}'
            if self._tcp_callback:
                loop = asyncio.get_running_loop()
                future = loop.run_in_executor(None, self._tcp_callback, payload)

                while True:
                    done, _ = await asyncio.wait({future}, timeout=10.0)
                    if done:
                        break
                    try:
                        await stream.write(b"\n")
                    except Exception:
                        future.cancel()
                        return stream

                try:
                    result = future.result()
                    body = result if isinstance(result, str) else json.dumps(result)
                except Exception as exc:
                    body = f'{{"error": "{str(exc)}"}}'

            await stream.write(body.encode('utf-8'))

        except Exception as exc:
            print(f"HTTP handler error: {exc}")
            error_body = f'{{"error": "{str(exc)}"}}'
            try:
                if not stream.prepared:
                    stream = web.StreamResponse(status=500, headers={'Content-Type': 'application/json'})
                    await stream.prepare(request)
                await stream.write(error_body.encode('utf-8'))
            except Exception:
                pass  # client already disconnected

        return stream

    async def start_listener(self):
        if self._app is not None:
            return  # already running

        self._app = web.Application()

        cors = aiohttp_cors.setup(self._app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=False,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["POST", "OPTIONS"],
            )
        })
        cors.add(self._app.router.add_post('/', self._handle_request))

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        self.connection_open = True
        print(f"HTTP server listening on http://{self.host}:{self.port}")

    async def stop_listener(self):
        if self._site is None:
            return

        await self._site.stop()
        await self._runner.cleanup()
        self._site = None
        self._runner = None
        self._app = None
        self.connection_open = False
        print("HTTP server stopped.")

    def toggle_sync(self, state: int, tcp_callback: Callable[[str], str]):
        if not self._event_loop:
            print("Error: event loop not set.")
            return

        self.set_callback_fn(tcp_callback)

        if state:
            asyncio.run_coroutine_threadsafe(self.start_listener(), self._event_loop)
        else:
            asyncio.run_coroutine_threadsafe(self.stop_listener(), self._event_loop)