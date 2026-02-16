import os
import sys
import shutil
import subprocess
from pathlib import Path

script_name = "EzUnBlock.py"
base_name = "ZapretGUI"
icon_path = Path("flags/z.ico")
build_dir = Path("dist")
spec_file = Path(f"{Path(script_name).stem}.spec")

try:
    import PyInstaller  # noqa: F401
except Exception:
    raise FileNotFoundError("❌ PyInstaller не установлен. Установи: pip install pyinstaller")

root = Path(__file__).resolve().parent
script_path = (root / script_name)
icon_abs = (root / icon_path)

# Проверка ресурсов
assert script_path.exists(), f"{script_path} не найден"
assert icon_abs.exists(), f"{icon_abs} не найден"
assert (root / "flags").exists(), "Папка flags не найдена"
assert (root / "core").exists(), "Папка core не найдена"
assert (root / "version.txt").exists(), "version.txt не найден"

# Очистка предыдущей сборки
for folder in (root / "build", root / "dist"):
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
if spec_file.exists():
    spec_file.unlink()

sep = os.pathsep

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    f"--icon={str(icon_abs)}",
    f"--name={base_name}",
    f"--add-data={str(root/'flags')}{sep}flags",
    f"--add-data={str(root/'core')}{sep}core",
    "--version-file", str(root / "version.txt"),

    "--hidden-import=psutil",
    "--hidden-import=requests",
    "--hidden-import=urllib3",
    "--hidden-import=idna",
    "--hidden-import=charset_normalizer",
    "--hidden-import=certifi",

    str(script_path)
]

print("▶ Сборка exe файла...")
subprocess.run(cmd, check=True, cwd=str(root))
print("✅ Сборка завершена!")

src_exe = build_dir / f"{base_name}.exe"
assert src_exe.exists(), f"❌ Не найден результат сборки: {src_exe}"

final_exe = build_dir / f"{base_name}.exe"

if final_exe.exists() and final_exe != src_exe:
    final_exe.unlink()

if final_exe != src_exe:
    src_exe.rename(final_exe)

print(f"\n📦 Готовый файл: {final_exe}")
