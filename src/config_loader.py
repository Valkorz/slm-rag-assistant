import json
import os
import sys
from pathlib import Path

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

def save_config(root_model_path : str, previous_question : str, documents : list[dict], language : str, model_query : str, model_reason : str) -> None:
    json_obj = {
        "root_model_path":root_model_path,
        "previous_question":previous_question,
        "documents":documents,
        "language":language,
        "model_query":model_query,
        "model_reason":model_reason
    }

    config_path = Path("../config.json")
    with open(config_path, 'w', encoding='utf-8') as file:
        file.write(json.dumps(json_obj))
    pass

def get_config() -> dict:
    config_path = Path("../config.json")
    if not config_path.exists():
        return None
    
    json_str = ""
    with open(config_path, 'r', encoding='utf-8') as file:
        json_str = file.read()

    return json.loads(json_str)