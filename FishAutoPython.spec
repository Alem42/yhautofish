# -*- mode: python ; coding: utf-8 -*-

import os


block_cipher = None
model_datas = []
model_dir = os.path.join('models', 'easyocr')
if os.path.isdir(model_dir):
    for filename in ('craft_mlt_25k.pth', 'zh_sim_g2.pth'):
        source = os.path.join(model_dir, filename)
        if os.path.isfile(source):
            model_datas.append((source, model_dir))


a = Analysis(
    ['autofish.py'],
    pathex=[],
    binaries=[],
    datas=model_datas,
    hiddenimports=[
        'easyocr',
        'torch',
        'torchvision',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Avoid accidentally bundling old VC runtimes from unrelated PATH entries such
# as Java JDKs. PyTorch should either use the modern system runtime or the
# explicit copies below.
vc_runtime_names = {
    'msvcp140.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll',
}
a.binaries = [
    entry for entry in a.binaries
    if os.path.basename(entry[0]).lower() not in vc_runtime_names
]
system32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
for dll_name in sorted(vc_runtime_names):
    dll_path = os.path.join(system32, dll_name)
    if os.path.isfile(dll_path):
        a.binaries.append((dll_name, dll_path, 'BINARY'))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FishAutoPython',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FishAutoPython',
)
