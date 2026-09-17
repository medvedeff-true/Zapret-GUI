from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
import threading
from collections.abc import Callable
from pathlib import Path


InstallProgress = Callable[[int, int, str], None]
_INSTALL_LOCK = threading.Lock()
_OBSOLETE_NOTICE_SHA256 = "c61296687f8b8b22f0f171373d8da98c39ac895be0881880e3a5400de170f384"


class AdaptiveRuntimeError(RuntimeError):
    """Raised when the packaged validator runtime cannot be installed safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str) -> Path:
    normalized = str(value or "").replace("\\", "/").strip("/")
    relative = Path(normalized)
    if not normalized or relative.is_absolute() or ".." in relative.parts:
        raise AdaptiveRuntimeError(f"Некорректный путь в manifest: {value!r}")
    return relative


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse_point(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = int(getattr(os.lstat(path), "st_file_attributes", 0) or 0)
        return bool(attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AdaptiveRuntimeError(f"Не удалось проверить путь runtime: {path}: {exc}") from exc


def _ensure_safe_directory(root: Path, directory: Path) -> None:
    root = _absolute_without_resolving(root)
    directory = _absolute_without_resolving(directory)
    try:
        relative = directory.relative_to(root)
    except ValueError as exc:
        raise AdaptiveRuntimeError(f"Путь выходит за пределы adaptive runtime: {directory}") from exc

    parent = root.parent
    if parent.exists() and _is_reparse_point(parent):
        raise AdaptiveRuntimeError(f"Родительская папка adaptive runtime является ссылкой: {parent}")
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir() or _is_reparse_point(root):
        raise AdaptiveRuntimeError(f"Небезопасная папка adaptive runtime: {root}")

    current = root
    for part in relative.parts:
        current = current / part
        if current.exists():
            if not current.is_dir() or _is_reparse_point(current):
                raise AdaptiveRuntimeError(f"Небезопасная подпапка adaptive runtime: {current}")
            continue
        current.mkdir()
        if _is_reparse_point(current):
            raise AdaptiveRuntimeError(f"Небезопасная подпапка adaptive runtime: {current}")


def _temporary_sibling(destination: Path) -> Path:
    return destination.with_name(
        f".{destination.name}.{os.getpid()}.{secrets.token_hex(8)}.installing"
    )


def _remove_obsolete_notice(destination_root: Path) -> None:
    """Remove only the NOTICE file created by releases before runtime v2.

    The old file is no longer part of the validator runtime.  Restricting the
    cleanup to its known digest means a user's own NOTICE.txt is never touched.
    """
    notice = destination_root / "NOTICE.txt"
    try:
        if (
            notice.is_file()
            and not _is_reparse_point(notice)
            and _sha256(notice) == _OBSOLETE_NOTICE_SHA256
        ):
            notice.unlink()
    except OSError:
        pass


def load_runtime_manifest(source_root: Path) -> dict:
    manifest_path = source_root / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdaptiveRuntimeError(f"Не найден manifest компонентов: {manifest_path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdaptiveRuntimeError(f"Не удалось прочитать manifest компонентов: {exc}") from exc

    if payload.get("schema") != 1 or not isinstance(payload.get("files"), list):
        raise AdaptiveRuntimeError("Неподдерживаемый формат manifest компонентов")
    return payload


def ensure_adaptive_runtime(
    source_root: Path,
    destination_root: Path,
    progress: InstallProgress | None = None,
) -> dict[str, int | str]:
    """Install or repair the shared validator runtime without deleting user data.

    Existing files are reused only when both their size and SHA-256 match the
    packaged manifest.  Unknown files are intentionally left untouched, apart
    from the precisely identified obsolete NOTICE.txt from older releases.
    """
    source_root = source_root.resolve()
    destination_root = _absolute_without_resolving(destination_root)
    callback = progress or (lambda _done, _total, _name: None)

    with _INSTALL_LOCK:
        manifest = load_runtime_manifest(source_root)
        entries = manifest["files"]
        total = max(1, len(entries))
        copied = 0
        reused = 0
        _ensure_safe_directory(destination_root, destination_root)

        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise AdaptiveRuntimeError("Повреждён manifest компонентов")
            relative = _safe_relative_path(str(entry.get("path") or ""))
            expected_hash = str(entry.get("sha256") or "").lower()
            try:
                expected_size = int(entry.get("size"))
            except (TypeError, ValueError) as exc:
                raise AdaptiveRuntimeError(f"Некорректный размер {relative}") from exc
            if not expected_hash or len(expected_hash) != 64 or expected_size < 0:
                raise AdaptiveRuntimeError(f"Некорректная контрольная сумма {relative}")

            source = source_root / relative
            destination = destination_root / relative
            callback(index - 1, total, relative.as_posix())

            if destination.exists() and _is_reparse_point(destination):
                raise AdaptiveRuntimeError(f"Компонент runtime является ссылкой: {relative}")

            destination_ok = False
            try:
                destination_ok = (
                    destination.is_file()
                    and destination.stat().st_size == expected_size
                    and _sha256(destination) == expected_hash
                )
            except OSError:
                destination_ok = False
            if destination_ok:
                reused += 1
                callback(index, total, relative.as_posix())
                continue

            try:
                source_ok = (
                    source.is_file()
                    and source.stat().st_size == expected_size
                    and _sha256(source) == expected_hash
                )
            except OSError:
                source_ok = False
            if not source_ok:
                raise AdaptiveRuntimeError(f"Компонент отсутствует или повреждён: {relative}")

            _ensure_safe_directory(destination_root, destination.parent)
            temporary = _temporary_sibling(destination)
            try:
                with source.open("rb") as source_handle, temporary.open("xb") as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
                if temporary.stat().st_size != expected_size or _sha256(temporary) != expected_hash:
                    raise AdaptiveRuntimeError(f"Ошибка проверки скопированного файла: {relative}")
                os.replace(temporary, destination)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            copied += 1
            callback(index, total, relative.as_posix())

        # Cygwin warns when /tmp is missing.  It contains only transient files.
        _ensure_safe_directory(destination_root, destination_root / "cygwin" / "tmp")
        _remove_obsolete_notice(destination_root)
        manifest_target = destination_root / "manifest.json"
        manifest_bytes = (source_root / "manifest.json").read_bytes()
        if manifest_target.exists() and _is_reparse_point(manifest_target):
            raise AdaptiveRuntimeError("Manifest adaptive runtime является ссылкой")
        if not manifest_target.is_file() or manifest_target.read_bytes() != manifest_bytes:
            temporary_manifest = _temporary_sibling(manifest_target)
            try:
                with temporary_manifest.open("xb") as handle:
                    handle.write(manifest_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_manifest, manifest_target)
            finally:
                temporary_manifest.unlink(missing_ok=True)

        callback(total, total, "")
        return {
            "copied": copied,
            "reused": reused,
            "total": len(entries),
            "version": str(manifest.get("version") or ""),
        }
