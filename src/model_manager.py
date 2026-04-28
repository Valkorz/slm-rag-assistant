from pathlib import Path
from typing import Optional 
from llama_cpp import Llama 
from huggingface_hub import hf_hub_download

class ModelManager:
    #List of verified models
    KNOWN_MODELS = {
        "gemma-4-e4b": {
            "repo": "google/gemma-4-E4B-it-GGUF",
            "file": "gemma-4-E4B-it-Q4_K_M.gguf",
            "description": "Gemma 4 E4B Instruct (recommended)"
        },
        "gemma-4-e2b": {
            "repo": "google/gemma-4-E2B-it-GGUF",
            "file": "gemma-4-E2B-it-Q4_K_M.gguf",
            "description": "Gemma 4 E2B Instruct (lightweight)"
        },
        "Llama-3.1-8b": {
            "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
            "file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            "description": "Llama 3.1 8B Instruct"
        },
    }

    _models_folder_paths : list[dict]
    _root_model_path : str

    def __init__(self, models_root_path: Optional[str] = None):
        self.models_dir = Path(models_root_path or (Path.home() / ".rag_assistant" / "models"))
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._root_model_path = str(self.models_dir)
        self._loaded_model: Optional[Llama] = None
        self._loaded_model_name: Optional[str] = None
        self._models_folder_paths = []
        self.find_models_root_path(self._root_model_path)

    def set_models_root_path(self, root_path: str) -> None:
        self.models_dir = Path(root_path)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._root_model_path = str(self.models_dir)
        self.find_models_root_path(self._root_model_path)

    def get_models_root_path(self) -> str:
        return self._root_model_path

    def list_available(self) -> list[dict]:
        available = []
        for name, info in self.KNOWN_MODELS.items():
            path = self.models_dir / info["file"]
            print(f"known model path: {path}")
            available.append({
                "name": name,
                "description": info["description"],
                "file": info["file"],
                "downloaded": path.exists(),
                "size_gb": round(path.stat().st_size / 1e9, 2) if path.exists() else None,
                "path": str(path) if path.exists() else None
            })
        return available
    
    def list_available_by_name(self) -> list[str]:
        return [m['name'] for m in self.list_available()]

    def list_downloaded(self) -> list[str]:
        print(f"listing... {self._models_folder_paths}")
        return [m['name'] for m in self._models_folder_paths]
    
    def find_models_root_path(self, root_path : str) -> None:
        paths_stack = []
        self._models_folder_paths = []
        paths_stack.append(root_path)
        
        while len(paths_stack) > 0:
            current_path = paths_stack.pop()
            for item in Path(current_path).iterdir():
                if str(item.resolve()).endswith(".gguf"):
                    self._models_folder_paths.append(
                        {
                            "name":item.name,
                            "path":str(item.resolve())
                        }
                    )
                elif item.resolve().is_dir():
                    paths_stack.append(str(item.resolve()))
                    

    def _resolve_model_path(self, model_name: str) -> Optional[Path]:
        # First try a known model file name under the configured root.
        if model_name in self.KNOWN_MODELS:
            known_file = self.KNOWN_MODELS[model_name]["file"]
            direct_path = self.models_dir / known_file
            if direct_path.exists():
                return direct_path

            for model_entry in self._models_folder_paths:
                if model_entry["name"] == known_file:
                    return Path(model_entry["path"])

        # Then treat model_name as a GGUF file name.
        for model_entry in self._models_folder_paths:
            if model_entry["name"] == model_name:
                return Path(model_entry["path"])

        return None

    def download(self, model_name: str, progress_callback=None) -> str:
        if model_name not in self.KNOWN_MODELS:
            raise ValueError(
                f"Unknown model '{model_name}'. "
                f"Available: {list(self.KNOWN_MODELS.keys())}"
            )

        info = self.KNOWN_MODELS[model_name]
        dest = self.models_dir / info["file"]

        if dest.exists():
            print(f"'{model_name}' already downloaded at {dest}")
            return str(dest)

        print(f"⬇️  Downloading '{model_name}' from {info['repo']}...")
        print(f"    File: {info['file']}")
        print(f"    Destination: {self.models_dir}")

        path = hf_hub_download(
            repo_id=info["repo"],
            filename=info["file"],
            local_dir=str(self.models_dir),
            local_dir_use_symlinks=False,   
        )

        print(f"Download complete: {path}")
        return path
    
    def load(self, model_name: str, n_ctx: int = 8192, n_gpu_layers: int = -1) -> Llama:
        if self._loaded_model_name == model_name:
            return self._loaded_model  

        self.find_models_root_path(self._root_model_path)
        path = self._resolve_model_path(model_name)

        if path is None:
            raise FileNotFoundError(
                f"Model '{model_name}' was not found under '{self._root_model_path}'. "
                f"Set a valid root path and make sure a .gguf file exists there."
            )

        self.unload() 

        print(f"🔄 Loading '{model_name}'...")
        self._loaded_model = Llama(
            model_path=str(path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False
        )
        self._loaded_model_name = model_name
        print(f"'{model_name}' loaded.")
        return self._loaded_model

    def unload(self):
        if self._loaded_model is not None:
            del self._loaded_model
            self._loaded_model = None
            self._loaded_model_name = None

    def generate(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        stop: Optional[list[str]] = None
    ) -> str:
        if model_name and model_name != self._loaded_model_name:
            self.load(model_name)

        if self._loaded_model is None:
            raise RuntimeError("No model loaded. Call load() first.")

        response = self._loaded_model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
            echo=False
        )
        return response["choices"][0]["text"].strip()

    def create_completion(self, prompt: str, **kwargs) -> dict:
        text = self.generate(prompt, **kwargs)
        return {
            "choices": [{"text": text, "finish_reason": "stop"}]
        }