import asyncio
import json
from typing import Callable, Optional

class AssistantRequestSocket:

    # Public
    connection_open: bool = False
    host: str
    port: int

    # Private
    _tcp_callback: Optional[Callable[[str], str]] = None
    _server: Optional[asyncio.Server] = None
    _event_loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(self, host: str = "127.0.0.1", port: int = 8008):
        self.host = host
        self.port = port
        self._server = None
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

    def _extract_payload(self, message: str) -> tuple[str, bool]:
        lines = message.splitlines()
        if not lines:
            return message, False

        request_line = lines[0].strip().upper()
        is_http = request_line.startswith("GET ") or request_line.startswith("POST ") or request_line.startswith("PUT ") or request_line.startswith("DELETE ") or request_line.startswith("PATCH ")
        if not is_http:
            return message, False

        header_end = message.find("\r\n\r\n")
        if header_end != -1:
            return message[header_end + 4 :], True

        header_end = message.find("\n\n")
        if header_end != -1:
            return message[header_end + 2 :], True

        return "", True

    def _build_http_response(self, payload: str, status_code: int = 200) -> bytes:
        reason = "OK" if status_code == 200 else "Bad Request"
        body = payload if isinstance(payload, str) else json.dumps(payload)
        body_bytes = body.encode("utf-8")
        headers = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        return headers.encode("utf-8") + body_bytes

    async def start_listener(self):
        if self._server is not None:
            return  # already running

        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port
        )
        self.connection_open = True
        print(f"TCP server listening on {self.host}:{self.port}")

        async with self._server:
            await self._server.serve_forever()

    async def stop_listener(self):
        if self._server is None:
            return

        self._server.close()
        await self._server.wait_closed()
        self._server = None
        self.connection_open = False
        print("TCP server stopped.")

    def toggle_sync(self, state: int, tcp_callback: Callable[[str], str]):
        if not self._event_loop:
            print("Error: event loop not set.")
            return

        self.set_callback_fn(tcp_callback)

        if state:
            asyncio.run_coroutine_threadsafe(self.start_listener(), self._event_loop)
        else:
            asyncio.run_coroutine_threadsafe(self.stop_listener(), self._event_loop)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.read(4096)
            message = data.decode().strip()
            addr = writer.get_extra_info("peername")
            print(f"TCP request from {addr}: {message}")

            response = '{"error": "No callback registered."}'
            status_code = 200
            payload, is_http = self._extract_payload(message)

            if self._tcp_callback:
                try:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None,
                        self._tcp_callback,
                        payload,
                    )
                    response = result if isinstance(result, str) else json.dumps(result)
                except Exception as exc:
                    response = f'{{"error": "{str(exc)}"}}'
                    status_code = 400

            if is_http:
                writer.write(self._build_http_response(response, status_code=status_code))
            else:
                writer.write(response.encode("utf-8") if isinstance(response, str) else response)
            await writer.drain()

        except Exception as exc:
            print(f"TCP handler error: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()