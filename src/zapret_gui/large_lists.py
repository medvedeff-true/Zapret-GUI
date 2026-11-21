"""Bounded-memory, stable-order runtime-list generation.

Small lists use an in-memory set. Large lists spill exact deduplication to a
temporary SQLite B-tree (not a probabilistic filter). No database survives a
merge. Only source/output stat signatures are cached between launches.
"""
from __future__ import annotations

from contextlib import ExitStack
import codecs
import csv
from functools import wraps
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading

MEMORY_THRESHOLD = 4 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
_LOCK = threading.RLock()


def _serialized(function):
    @wraps(function)
    def locked(*args, **kwargs):
        with _LOCK:
            return function(*args, **kwargs)
    return locked


def signature(path: str | Path) -> list | None:
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return None
    return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]


def iter_lines(path: str | Path):
    """Stream normalized UTF-8 list entries, bounding even a malformed line."""
    try:
        stream = open(path, "rb", buffering=256 * 1024)
    except FileNotFoundError:
        return
    with stream:
        first = True
        while True:
            data = stream.readline(MAX_LINE_BYTES + 1)
            if not data:
                return
            if len(data) > MAX_LINE_BYTES:
                raise ValueError(f"Слишком длинная строка списка: {Path(path).name} (больше 64 КиБ)")
            try:
                value = data.decode("utf-8-sig" if first else "utf-8").strip()
            except UnicodeDecodeError as error:
                raise ValueError(f"Список содержит невалидный UTF-8: {Path(path).name}") from error
            first = False
            if value and not value.startswith("#"):
                yield value


def iter_delimited_text_values(path: str | Path):
    """Yield text-list values without ever materializing the source file."""
    with open(path, "r", encoding=_import_encoding(path), buffering=256 * 1024) as source:
        while True:
            line = source.readline(MAX_LINE_BYTES + 1)
            if not line:
                return
            if len(line) > MAX_LINE_BYTES:
                raise ValueError(f"Слишком длинная строка импортируемого списка: {Path(path).name}")
            cleaned = line.split("#", 1)[0].strip()
            if cleaned:
                yield from (part.strip() for part in re.split(r"[;,]", cleaned) if part.strip())


def _import_encoding(path: str | Path) -> str:
    with open(path, "rb") as source:
        sample = source.read(MAX_LINE_BYTES)
    if sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        codecs.getincrementaldecoder("utf-8-sig")().decode(sample, final=False)
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1251"


def iter_csv_values(path: str | Path):
    try:
        stream = open(path, "r", encoding=_import_encoding(path), newline="", buffering=256 * 1024)
    except FileNotFoundError:
        return
    with stream:
        for row in csv.reader(stream):
            for cell in row:
                yield from (part.strip() for part in re.split(r"[;,]", cell) if part.strip())


@_serialized
def append_unique_value(path: str | Path, value: str) -> bool:
    """Append one normalized entry with O(1) extra memory."""
    path = Path(path)
    value = value.strip()
    if not value:
        return False
    key = value.casefold()
    if path.exists():
        for current in iter_lines(path):
            if current.casefold() == key:
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as stream:
            stream.seek(-1, os.SEEK_END)
            if stream.read(1) != b"\n":
                prefix = "\n"
    with path.open("ab", buffering=256 * 1024) as stream:
        stream.write((prefix + value + "\n").encode("utf-8"))
    return True


@_serialized
def remove_values(path: str | Path, values) -> int:
    """Rewrite a list atomically while retaining only unselected entries."""
    path = Path(path)
    selected = {str(value).strip().casefold() for value in values if str(value).strip()}
    if not selected or not path.exists():
        return 0
    removed = 0
    temporary = None
    try:
        with path.open("rb") as source, tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=path.name + "-", suffix=".tmp", delete=False,
        ) as output:
            temporary = Path(output.name)
            first = True
            while True:
                raw = source.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError(f"Слишком длинная строка списка: {path.name}")
                value = raw.decode("utf-8-sig" if first else "utf-8").strip()
                first = False
                if value and value.casefold() in selected:
                    removed += 1
                else:
                    output.write(raw)
        os.replace(temporary, path)
        temporary = None
        return removed
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def normalized_values_file(target_file: str | Path, values, normalize, validate) -> tuple[Path, int]:
    """Create a temporary normalized import stream, returning valid count."""
    parent = Path(target_file).parent
    parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix="import-", suffix=".txt", dir=parent)
    os.close(descriptor)
    temporary = Path(filename)
    count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="\n", buffering=256 * 1024) as output:
            for raw in values:
                value = normalize(raw)
                if value and validate(value):
                    output.write(value + "\n")
                    count += 1
        return temporary, count
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def merge_import_file(target_file: str | Path, import_file: str | Path) -> int:
    """Merge an import stream into a user list and always remove the stream."""
    stats = {}
    try:
        merge_files(target_file, [target_file, import_file], stats=stats, use_cache=False)
        return stats.get("added", 0)
    finally:
        Path(import_file).unlink(missing_ok=True)


def base_list_path(paths) -> str:
    """Match the old source/bundled/runtime fallback without loading a file."""
    for index, path in enumerate(paths):
        if os.path.isfile(path):
            if index == 0 and not any(iter_lines(path)):
                # Match the historical fallback for an empty managed seed.
                continue
            return str(path)
    return str(paths[0])


def merge_files(
    destination: str | Path,
    sources,
    *,
    stats: dict | None = None,
    use_cache: bool = True,
    validate=None,
    validation_tag: str = "",
) -> bool:
    """Atomically merge lists. Return False on a verified unchanged cache hit."""
    destination = Path(destination)
    sources = [str(Path(path).absolute()) for path in sources]
    with _LOCK:
        state = {
            "version": 2,
            "validation": str(validation_tag or ""),
            "sources": [[path, signature(path)] for path in sources],
        }
        cache = Path(str(destination) + ".merge.json")
        if use_cache:
            try:
                previous = json.loads(cache.read_text(encoding="utf-8"))
                if previous.get("inputs") == state and previous.get("output") == signature(destination):
                    return False
            except (OSError, ValueError):
                pass
        destination.parent.mkdir(parents=True, exist_ok=True)
        large = sum(item[1][0] for item in state["sources"] if item[1]) > MEMORY_THRESHOLD
        temporary = None
        try:
            with ExitStack() as stack:
                output = stack.enter_context(tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", newline="\n", buffering=256 * 1024,
                    prefix=destination.name + "-", suffix=".tmp",
                    dir=destination.parent, delete=False,
                ))
                temporary = Path(output.name)
                seen = set()
                cursor = None
                if large:
                    directory = stack.enter_context(tempfile.TemporaryDirectory(
                        prefix="list-index-", dir=destination.parent))
                    database = sqlite3.connect(str(Path(directory) / "seen.sqlite"))
                    stack.callback(database.close)
                    database.executescript("""
                        PRAGMA journal_mode=OFF;
                        PRAGMA synchronous=OFF;
                        PRAGMA temp_store=FILE;
                        PRAGMA cache_size=-4096;
                        CREATE TABLE seen (key TEXT PRIMARY KEY) WITHOUT ROWID;
                        BEGIN;
                    """)
                    cursor = database.cursor()
                added = 0
                for source_index, path in enumerate(sources):
                    for value in iter_lines(path):
                        if validate is not None:
                            try:
                                if not validate(value):
                                    continue
                            except Exception:
                                # A malformed entry must never abort the
                                # entire runtime-list rebuild.
                                continue
                        key = value.casefold()
                        if cursor is not None:
                            cursor.execute("INSERT OR IGNORE INTO seen VALUES (?)", (key,))
                            if not cursor.rowcount:
                                continue
                        else:
                            if key in seen:
                                continue
                            seen.add(key)
                        output.write(value + "\n")
                        if source_index:
                            added += 1
                if cursor is not None:
                    database.commit()
                if state["sources"] != [[path, signature(path)] for path in sources]:
                    raise ValueError("Списки изменились при подготовке запуска. Повторите запуск.")
            os.replace(temporary, destination)
            temporary = None
            if stats is not None:
                stats["added"] = added
            # This is only an optimization. Losing the cache cannot lose data.
            if use_cache:
                try:
                    state_text = json.dumps({"inputs": state, "output": signature(destination)})
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", dir=destination.parent,
                        prefix=cache.name + "-", suffix=".tmp", delete=False,
                    ) as stream:
                        cache_temp = Path(stream.name)
                        stream.write(state_text)
                    try:
                        os.replace(cache_temp, cache)
                    finally:
                        cache_temp.unlink(missing_ok=True)
                except OSError:
                    pass
            return True
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
