import io
import os
import sys
from pathlib import Path
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

#Queues messages sent during a session and saves them to a file once the session is finished
#(Singleton)
class Logger:
    #public
    IsSessionActive : bool

    #private
    _instance = None  # the single shared instance (see __new__)
    _ERROR_ICON         = f"{project_root}/images/cancel.png"
    _WARN_ICON          = f"{project_root}/images/crisis.png"
    _DEBUG_ICON         = f"{project_root}/images/debug.png"
    _INFORMATION_ICON   = f"{project_root}/images/information.png"
    _ICONS_DICT = {
        "ERROR"     :  _ERROR_ICON,
        "WARN"      :  _WARN_ICON,
        "DEBUG"     :  _DEBUG_ICON,
        "INFO"      :  _INFORMATION_ICON
    }

    _messages           : list[str]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.IsSessionActive = True
        self._messages = []

    def info(self, message : str):
        self._messages.append(f"[Info]\t@{datetime.now()}:\t{message}")
        pass

    def warn(self, message : str):
        self._messages.append(f"[Warn]\t@{datetime.now()}:\t{message}")
        pass

    def debug(self, message : str):
        self._messages.append(f"[Debug]\t@{datetime.now()}:\t{message}")
        pass

    def error(self, message : str):
        self._messages.append(f"[Error]\t@{datetime.now()}:\t{message}")
        pass

    def get_messages(self, count : int, icons : bool = False) -> list[dict]:
        if not icons:
            return self._messages[-count:]

        result = []
        for m in self._messages[-count:]:
            level = m[1:m.index("]")].upper() if m.startswith("[") and "]" in m else ""
            result.append({"message": m, "icon": self._ICONS_DICT.get(level)})
        return result
        
    def dump(self):
        self._messages.append(f"-- Logging finished: {datetime.now()} --")

        datetime_str = f"{datetime.now()}".replace(':', '-').replace('.', '_')
        fname = f"log_{datetime_str}.txt"
        if getattr(sys, 'frozen', False):
            dir = Path(os.path.dirname(sys.executable)) / "logs"
        dir = Path(__file__).resolve().parent.parent / "logs"
        dir.mkdir(parents=True, exist_ok=True)

        fpath = dir / fname
        with open(fpath, 'w', encoding='utf-8') as file:
            file.write(f"-- Logging started --\n\n")
            for msg in self._messages:
                file.write(f"{msg}\n")

        self.IsSessionActive = False
        self._messages = []
        pass


# Shared singleton instance — import this anywhere with:
#     from src.utils.logger import logger
logger = Logger()
        
