"""Legacy compatibility alias for the packaged ZapretGUI application."""

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from site import addsitedir
    addsitedir(str(_SRC_DIR))
except Exception:
    pass

from zapret_gui import app as _application  # noqa: E402

if __name__ == "__main__":
    _application.main()
else:
    # Preserve the historical ``import EzUnBlock as app`` behavior, including
    # underscore-prefixed helpers and monkeypatching of their module globals.
    sys.modules[__name__] = _application
