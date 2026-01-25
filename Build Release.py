import os
import sys
import shutil
import subprocess

# Параметры
script_name = "EzUnBlock.py"
exe_name = "Zapret GUI.exe"
icon_path = "flags/z.ico"
build_dir = "dist"
spec_file = f"{os.path.splitext(script_name)[0]}.spec"

# Запускаем pyinstaller через текущий интерпретатор (venv), это надёжнее, чем искать exe
try:
    import PyInstaller  # noqa
except Exception:
    raise FileNotFoundError("❌ PyInstaller не установлен в этом окружении. Установи: pip install pyinstaller")

# Проверка ресурсов
assert os.path.exists(script_name), f"{script_name} не найден"
assert os.path.exists(icon_path), f"{icon_path} не найден"
assert os.path.exists("flags"), "Папка flags не найдена"
assert os.path.exists("core"), "Папка core не найдена"
assert os.path.exists("version.txt"), "version.txt не найден"

# Очистка предыдущей сборки
for folder in ("build", "dist"):
    if os.path.exists(folder):
        shutil.rmtree(folder)
if os.path.exists(spec_file):
    os.remove(spec_file)

# Команда сборки
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    f"--icon={icon_path}",
    f"--name={exe_name}",
    "--add-data=flags;flags",
    "--add-data=core;core",
    "--version-file=version.txt",
    "--hidden-import=psutil",
    script_name
]

print("▶ Сборка exe файла...")
subprocess.run(cmd, check=True)
print("✅ Сборка завершена!")

# Проверка итогового exe
src_exe = os.path.join(build_dir, exe_name)
if not os.path.exists(src_exe):
    fallback = os.path.join(build_dir, "Zapret GUI.exe")
    if os.path.exists(fallback):
        os.rename(fallback, src_exe)
    else:
        raise FileNotFoundError("❌ Файл .exe не найден после сборки")

print(f"\n📦 Готовый файл: {src_exe}")
