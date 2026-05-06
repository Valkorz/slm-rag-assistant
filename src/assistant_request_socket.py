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
    _model_prompt_routine_callback: Optional[Callable[[str,str,str,str],str]]
    _server: Optional[asyncio.Server] = None
    _event_loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(self, host: str = "127.0.0.1", port: int = 8008):
        self.host = host
        self.port = port
        self._server = None
        self._event_loop = None

    def parse_response(self, response : str) -> dict[str,str]:
        try:
            data = "{" + response.split('{')[1]
            return json.loads(data)
        except Exception as e:
            print(f"Error while parsing response: {str(e)}")
        
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._event_loop = loop

    def sethost(self, host: str):
        self.host = host

    def setport(self, port: int):
        self.port = port

    def set_callback_fn(self, callback: Optional[Callable[[str], str]]):
        self._tcp_callback = callback

    def set_prompt_callback(self, callback: Optional[Callable[[str,str,str,str],str]]):
        self._model_prompt_callback = callback

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
            # print(f"TCP request from {addr}: {message}")

            response = '{"error": "No callback registered."}'

            if self._tcp_callback and self._model_prompt_callback:
                try:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None,
                        self._tcp_callback,
                        message
                    )
                    response = result if isinstance(result, str) else str(result)
                    
                    msg_json = self.parse_response(message)
                    response = self._model_prompt_routine_callback(
                            msg_json['question'],
                            msg_json['lang'],
                            msg_json['model_query'],
                            msg_json['model_reason'])
                    
                except Exception as exc:
                    response = f'{{"error": "{str(exc)}"}}'
            
            writer.write(response)
            await writer.drain()

        except Exception as exc:
            print(f"TCP handler error: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()