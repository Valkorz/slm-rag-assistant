import json
import os
import sys
from pathlib import Path

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

def _config_path() -> Path:
    # When frozen by PyInstaller, write next to the executable.
    # When running from source, write to the project root.
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable)) / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"

def save_config(root_model_path : str, previous_question : str, documents : list[dict], language : str, model_query : str, model_reason : str, settings : dict = None) -> None:
    json_obj = {
        "root_model_path":root_model_path,
        "previous_question":previous_question,
        "documents":documents,
        "language":language,
        "model_query":model_query,
        "model_reason":model_reason,
        "settings": settings or {}
    }

    with open(_config_path(), 'w', encoding='utf-8') as file:
        file.write(json.dumps(json_obj))

def get_config() -> dict:
    config_path = _config_path()
    if not config_path.exists():
        return None

    with open(config_path, 'r', encoding='utf-8') as file:
        return json.loads(file.read())