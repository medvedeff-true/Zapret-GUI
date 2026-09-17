# ZapretGUI source modules

`EzUnBlock.py` remains the executable entry point and public compatibility module. It loads these ordered source fragments into its own namespace. This deliberately preserves the existing global references, public API, and test monkeypatching while keeping the implementation separated by responsibility. The files are intentionally ordered because the legacy implementation uses direct global references between sections; changing that order would be a behavior change.

The directory is passed to PyInstaller with `--add-data`, so a `--onefile` build embeds all fragments inside the EXE and extracts them only into PyInstaller's temporary runtime directory.

Load order:

- `runtime_setup.py`
- `app_config.py`
- `ui_base.py`
- `runtime_data.py`
- `dns_service.py`
- `list_management.py`
- `updates.py`
- `dialogs_and_workers.py`
- `adaptive_ui.py`
- `ui_controls.py`
- `site_manager.py`
- `main_window.py`
- `application_lifecycle.py`
