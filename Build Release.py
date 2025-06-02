import os
import shutil
import subprocess

# Параметры
script_name = "EzUnBlock.py"
exe_name = "Zapret GUI.exe"
icon_path = "flags/z.ico"
build_dir = "dist"
spec_file = f"{os.path.splitext(script_name)[0]}.spec"

# Проверка наличия нужных файлов
assert os.path.exists(script_name), f"{script_name} не найден"
assert os.path.exists(icon_path), f"{icon_path} не найден"
assert os.path.exists("flags"), "Папка flags не найдена"
assert os.path.exists("core"), "Папка core не найдена"

# Очистка предыдущей сборки
for folder in ("build", "dist"):
    if os.path.exists(folder):
        shutil.rmtree(folder)
if os.path.exists(spec_file):
    os.remove(spec_file)

# Команда сборки
cmd = [
    "pyinstaller",
    "--onefile",
    "--noconsole",
    f"--icon={icon_path}",
    f"--name={exe_name}",
    "--add-data=flags;flags",
    "--add-data=core;core",
    script_name
]

print("▶ Сборка exe файла...")
subprocess.run(cmd, check=True)

print("\n✅ Сборка завершена!")

src_exe = os.path.join(build_dir, exe_name)
if not os.path.exists(src_exe):
    fallback = os.path.join(build_dir, "Zapret GUI")
    if os.path.exists(fallback):
        os.rename(fallback, src_exe)
    else:
        raise FileNotFoundError("Файл .exe не найден после сборки")

print(f"\n📦 Готовый файл: {src_exe}")
