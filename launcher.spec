# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Collect all Streamlit files
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Add your app file
datas += [('summarizer_ui.py', '.')]
datas += [('src/*.py', 'src')]

# Add any other data files your app needs (uncomment as needed)
# datas += [('data/*.csv', 'data')]
# datas += [('assets/', 'assets')]

# Add hidden imports for your other dependencies
# Check your requirements.txt and add packages that might not be auto-detected
hiddenimports += [
    # Common packages that need explicit inclusion:
    # 'pandas',
    'streamlit',
    # Add others from your requirements.txt:
    'openai',
    # 'anthropic',
    # 'langchain',
    'youtube_transcript_api',
    # etc.
]

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Optional/unused integrations that can trigger noisy warnings during analysis.
        'langchain',
        'streamlit.external.langchain',
        # Large optional stacks that hook discovery may probe for.
        'tensorflow',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)