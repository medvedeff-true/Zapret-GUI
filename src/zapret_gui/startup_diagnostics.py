"""Best-effort startup logging, initialized before Qt or application imports."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading

logger = logging.getLogger("zapret_gui.startup")
logger.addHandler(logging.NullHandler())
log_path = None


def initialize():
    global log_path
    if log_path is not None:
        return
    try:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ZapretGUI" / "logs"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "startup.log"
        handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s pid=%(process)d %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        log_path = path
        previous_hook = sys.excepthook

        def exception_hook(kind, value, tb):
            logger.critical("Unhandled exception", exc_info=(kind, value, tb))
            previous_hook(kind, value, tb)

        sys.excepthook = exception_hook
        previous_thread_hook = threading.excepthook

        def thread_hook(args):
            logger.error("Thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            previous_thread_hook(args)

        threading.excepthook = thread_hook
        logger.info("Bootstrap executable=%r frozen=%s autostart=%s cwd=%r",
                    sys.executable, bool(getattr(sys, "frozen", False)),
                    "--autostart" in [a.casefold() for a in sys.argv[1:]], os.getcwd())
    except Exception:
        # A full/readonly disk must not itself prevent the GUI from starting.
        pass
