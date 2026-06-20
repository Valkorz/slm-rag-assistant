# assistant.spec
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect everything (code + data + binaries) for libraries that use
# dynamic imports or ship non-Python assets (themes, kernels, etc.)
packages_to_collect = [
    'customtkinter',
    'chromadb',
    'sentence_transformers',
    'llama_cpp',
    'tokenizers',
    'huggingface_hub',
]

all_datas    = []
all_binaries = []
all_hidden   = []

for pkg in packages_to_collect:
    d, b, h = collect_all(pkg)
    all_datas    += d
    all_binaries += b
    all_hidden   += h

all_datas += [
    ('images',  'images'),   # PDF icon used in the file list
    ('data',    'data'),     # default documents folder (may be empty)
]

a = Analysis(
    ['assistant.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden + [
        # aiohttp and its CORS extension use dynamic plugin loading
        'aiohttp',
        'aiohttp_cors',
        'aiohttp.web',
        'aiohttp.web_runner',
        # tiktoken encodings loaded at runtime
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        # sqlite3 backend used by ChromaDB
        'sqlite3',
        '_sqlite3',
        # onnxruntime used by ChromaDB's embedding pipeline
        'onnxruntime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'notebook',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # keeps binaries in the folder, not the exe
    name='SLM-RAG-Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX compression can corrupt ML binaries — keep off
    console=True,           # no terminal window; change to True to see print() output
    icon=None,               # replace with 'images/icon.ico' if you add one
)

# --onedir build: everything goes into dist/SLM-RAG-Assistant/
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SLM-RAG-Assistant',
)
