"""Build the small .NET Framework service without downloading a toolchain."""
from pathlib import Path
import ast
import os
import subprocess
import tempfile


def build() -> Path:
    root = Path(__file__).resolve().parent
    project_root = root.parents[1]
    compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        compiler = compiler.parent.parent.parent / "Framework/v4.0.30319/csc.exe"
    target_dir = project_root / "resources" / "background_service"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "ZapretGUI.Service.exe"
    # Compile the app's fixed Telegram mapping into the trusted helper. The IPC
    # caller cannot supply hosts contents or a destination path to SYSTEM.
    config_source = project_root / "src" / "zapret_gui" / "app_modules" / "app_config.py"
    tree = ast.parse(config_source.read_text(encoding="utf-8-sig"))
    mapping = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "FLOWSEAL_TELEGRAM_WEB_HOSTS" for target in node.targets))
    with tempfile.TemporaryDirectory(prefix="zapret-gui-service-") as temp_dir:
        resource = Path(temp_dir) / "telegram-hosts.txt"
        resource.write_text("".join(ip + " " + host + "\n" for ip, host in mapping), encoding="utf-8")
        subprocess.run([
            str(compiler), "/nologo", "/target:winexe", "/platform:anycpu", "/optimize+",
            "/reference:System.ServiceProcess.dll", "/reference:System.Web.Extensions.dll",
            "/resource:" + str(resource) + ",TelegramHosts",
            "/out:" + str(target), str(root / "Service.cs"),
        ], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return target


if __name__ == "__main__":
    print(build())
