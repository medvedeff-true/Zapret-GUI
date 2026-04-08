import os
import sys
import shutil
import subprocess
import importlib
from pathlib import Path


script_name = "EzUnBlock.py"
base_name = "ZapretGUI"
icon_path = Path("flags/z.ico")
build_dir = Path("dist")
spec_files = (
    Path(f"{base_name}.spec"),
    Path(f"{Path(script_name).stem}.spec"),
)

required_modules = {
    "PyInstaller": "pyinstaller",
    "PyQt6": "PyQt6",
    "requests": "requests",
    "psutil": "psutil",
}

missing_modules = []
for module_name, package_name in required_modules.items():
    try:
        importlib.import_module(module_name)
    except Exception:
        missing_modules.append(package_name)

if missing_modules:
    missing_str = ", ".join(missing_modules)
    raise FileNotFoundError(
        f"Missing build dependencies: {missing_str}\n"
        f"Install with: {sys.executable} -m pip install {' '.join(missing_modules)}"
    )

root = Path(__file__).resolve().parent
script_path = root / script_name
icon_abs = root / icon_path

# Resource checks
assert script_path.exists(), f"{script_path} not found"
assert icon_abs.exists(), f"{icon_abs} not found"
assert (root / "flags").exists(), "flags folder not found"
assert (root / "core").exists(), "core folder not found"
assert (root / "version.txt").exists(), "version.txt not found"

# Clean previous build
for folder in (root / "build", root / "dist"):
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)

for spec_file in spec_files:
    spec_abs = root / spec_file
    if spec_abs.exists():
        spec_abs.unlink()

sep = os.pathsep

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--clean",
    "--noconfirm",
    f"--icon={icon_abs}",
    f"--name={base_name}",
    f"--add-data={root / 'flags'}{sep}flags",
    f"--add-data={root / 'core'}{sep}core",
    "--version-file", str(root / "version.txt"),
    "--hidden-import=PyQt6.sip",
    "--hidden-import=psutil",
    "--hidden-import=requests",
    "--hidden-import=urllib3",
    "--hidden-import=idna",
    "--hidden-import=charset_normalizer",
    "--hidden-import=certifi",
    str(script_path),
]

print("Building exe...")
subprocess.run(cmd, check=True, cwd=str(root))
print("Build completed!")

src_exe = build_dir / f"{base_name}.exe"
assert src_exe.exists(), f"Build result not found: {src_exe}"

print(f"\nReady: {src_exe}")
