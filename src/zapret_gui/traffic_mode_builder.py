"""Build winws arguments for traffic-processing modes.

This module deliberately only builds command-line text.  It does not touch
the system DNS configuration, the Windows hosts file, WinDivert, or any
process.  Keeping this boundary small makes the mode logic safe to test and
allows the privileged service to remain the only component that starts
``winws.exe``.

``all`` mode preserves the strategy selected by the user.  ``lists`` mode
projects each strategy segment onto the selected user list files only:

* ``--hostlist``      -> selected domain-add files;
* ``--ipset``         -> selected IP-add files;
* ``--hostlist-exclude`` and ``--ipset-exclude`` -> matching exclusions.

Segments which do not have a positive hostlist/ipset selector are omitted in
``lists`` mode.  This is important: retaining a strategy segment containing
only ``--filter-tcp`` or ``--filter-l7`` would silently turn "Only lists" into
a whole-traffic mode.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shlex
from typing import Iterable, Literal, Mapping, Sequence


TrafficMode = Literal["all", "lists"]
ListKind = Literal["domains_add", "domains_exclude", "ip_add", "ip_exclude"]

_LIST_OPTIONS: dict[str, ListKind] = {
    "--hostlist": "domains_add",
    "--hostlist-exclude": "domains_exclude",
    "--ipset": "ip_add",
    "--ipset-exclude": "ip_exclude",
}

# This option selects literal host names from the strategy and is deliberately
# not retained in list-only mode.  Only user-selected list files are allowed
# to select traffic there.
_HOSTLIST_DOMAIN_OPTION = "--hostlist-domains"
_SEGMENT_SEPARATOR = "--new"


@dataclass(frozen=True)
class UserListSelection:
    """Selected user list files for the ``lists`` traffic mode.

    Paths may be relative, quoted, duplicated, missing, or point to empty
    files.  The builder normalizes them and silently ignores files which
    cannot select anything.  This makes stale settings harmless after a file
    was moved or removed.
    """

    domains_add: tuple[os.PathLike[str] | str, ...] = ()
    domains_exclude: tuple[os.PathLike[str] | str, ...] = ()
    ip_add: tuple[os.PathLike[str] | str, ...] = ()
    ip_exclude: tuple[os.PathLike[str] | str, ...] = ()

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Iterable[os.PathLike[str] | str]] | None,
    ) -> "UserListSelection":
        if not value:
            return cls()
        return cls(
            domains_add=_as_path_tuple(value.get("domains_add", ())),
            domains_exclude=_as_path_tuple(value.get("domains_exclude", ())),
            ip_add=_as_path_tuple(value.get("ip_add", ())),
            ip_exclude=_as_path_tuple(value.get("ip_exclude", ())),
        )


@dataclass(frozen=True)
class _ParsedToken:
    text: str
    option: str = ""
    value: str | None = None
    has_value: bool = False


def _as_path_tuple(value: Iterable[os.PathLike[str] | str] | os.PathLike[str] | str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, os.PathLike)):
        return (os.fspath(value),)
    return tuple(os.fspath(item) for item in value)


def normalize_path(path: os.PathLike[str] | str, *, base_dir: os.PathLike[str] | str | None = None) -> str:
    """Return a stable absolute path without requiring the file to exist.

    ``realpath`` is intentionally not used: a missing path must still be
    normalized so stale settings can be compared and discarded predictably.
    Unexpanded ``%VAR%`` placeholders are left untouched because strategy
    files can legitimately contain Windows variables which are expanded later
    by the launch layer.
    """

    raw = os.fspath(path).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1]
    raw = os.path.expanduser(os.path.expandvars(raw))
    if "%" in raw:
        return os.path.normpath(raw)
    if base_dir is not None and not os.path.isabs(raw):
        raw = os.path.join(os.fspath(base_dir), raw)
    return os.path.abspath(os.path.normpath(raw))


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _has_selectable_entry(path: str) -> bool:
    """Return whether a list file contains at least one non-comment line."""

    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as stream:
            for line in stream:
                value = line.strip()
                if value and not value.startswith(("#", ";")):
                    return True
    except (OSError, UnicodeError):
        return False
    return False


def _usable_paths(
    paths: Iterable[os.PathLike[str] | str],
    *,
    base_dir: os.PathLike[str] | str | None,
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        path = normalize_path(raw, base_dir=base_dir)
        key = _path_key(path)
        if key in seen or not _has_selectable_entry(path):
            continue
        seen.add(key)
        result.append(path)
    return tuple(result)


def _parse_token(token: str) -> _ParsedToken:
    if not token.startswith("--"):
        return _ParsedToken(token)
    name, separator, value = token.partition("=")
    option = name.casefold()
    if not separator:
        return _ParsedToken(token, option=option)
    return _ParsedToken(token, option=option, value=_unquote(value), has_value=True)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _tokenize(segment: str) -> list[_ParsedToken]:
    try:
        raw_tokens = shlex.split(segment, posix=False)
    except ValueError:
        # A malformed profile should fail in the regular profile validator.
        # Keeping the raw segment here is safer than accidentally broadening
        # list-only traffic due to a best-effort parser.
        return []

    result: list[_ParsedToken] = []
    index = 0
    while index < len(raw_tokens):
        token = raw_tokens[index]
        parsed = _parse_token(token)
        if (
            parsed.option in _LIST_OPTIONS
            or parsed.option == _HOSTLIST_DOMAIN_OPTION
        ) and not parsed.has_value and index + 1 < len(raw_tokens):
            next_token = raw_tokens[index + 1]
            if not next_token.startswith("--"):
                parsed = _ParsedToken(
                    text=f"{token}={next_token}",
                    option=parsed.option,
                    value=_unquote(next_token),
                    has_value=True,
                )
                index += 1
        result.append(parsed)
        index += 1
    return result


def _quote_path(path: str) -> str:
    # winws accepts the same conventional quoted path syntax used by the
    # existing strategy BAT files.  User-controlled list paths cannot safely
    # be emitted unquoted because they may contain spaces.
    return f'"{path.replace(chr(34), chr(92) + chr(34))}"'


def _list_option(option: str, path: str) -> str:
    return f"{option}={_quote_path(path)}"


def _normalized_all_segment(
    tokens: Sequence[_ParsedToken],
    *,
    base_dir: os.PathLike[str] | str | None,
) -> str:
    output: list[str] = []
    for token in tokens:
        if token.option in _LIST_OPTIONS and token.has_value and token.value is not None:
            output.append(
                _list_option(
                    token.option,
                    normalize_path(token.value, base_dir=base_dir),
                )
            )
        else:
            output.append(token.text)
    return " ".join(output).strip()


def _selected_paths(
    selection: UserListSelection,
    *,
    base_dir: os.PathLike[str] | str | None,
) -> dict[ListKind, tuple[str, ...]]:
    return {
        "domains_add": _usable_paths(selection.domains_add, base_dir=base_dir),
        "domains_exclude": _usable_paths(selection.domains_exclude, base_dir=base_dir),
        "ip_add": _usable_paths(selection.ip_add, base_dir=base_dir),
        "ip_exclude": _usable_paths(selection.ip_exclude, base_dir=base_dir),
    }


def _lists_segments(
    tokens: Sequence[_ParsedToken],
    selected: Mapping[ListKind, tuple[str, ...]],
) -> list[str]:
    positive_kinds: list[ListKind] = []
    first_removed_index: int | None = None
    retained: list[_ParsedToken] = []

    for token in tokens:
        kind = _LIST_OPTIONS.get(token.option)
        if kind is not None:
            if (
                token.has_value
                and kind in ("domains_add", "ip_add")
                and kind not in positive_kinds
            ):
                positive_kinds.append(kind)
            if first_removed_index is None:
                first_removed_index = len(retained)
            continue
        if token.option == _HOSTLIST_DOMAIN_OPTION:
            if first_removed_index is None:
                first_removed_index = len(retained)
            continue
        retained.append(token)

    if not positive_kinds:
        return []

    if first_removed_index is None:
        first_removed_index = len(retained)
    first_removed_index = min(first_removed_index, len(retained))

    result: list[str] = []
    for positive_kind in positive_kinds:
        paths = selected[positive_kind]
        if not paths:
            continue
        if positive_kind == "domains_add":
            positive_option = "--hostlist"
            exclude_option = "--hostlist-exclude"
            exclude_paths = selected["domains_exclude"]
        else:
            positive_option = "--ipset"
            exclude_option = "--ipset-exclude"
            exclude_paths = selected["ip_exclude"]

        replacement = [
            _ParsedToken(_list_option(positive_option, path))
            for path in paths
        ]
        replacement.extend(
            _ParsedToken(_list_option(exclude_option, path))
            for path in exclude_paths
        )
        merged = retained[:first_removed_index] + replacement + retained[first_removed_index:]
        result.append(" ".join(token.text for token in merged).strip())
    return result


def _without_trailing_separator(segment: str) -> str:
    value = segment.rstrip()
    if value.casefold().endswith(" " + _SEGMENT_SEPARATOR):
        return value[: -(len(_SEGMENT_SEPARATOR) + 1)].rstrip()
    if value.casefold() == _SEGMENT_SEPARATOR:
        return ""
    return value


def build_traffic_segments(
    strategy_segments: Iterable[str],
    *,
    mode: TrafficMode = "all",
    selected_lists: UserListSelection | Mapping[str, Iterable[os.PathLike[str] | str]] | None = None,
    base_dir: os.PathLike[str] | str | None = None,
) -> tuple[str, ...]:
    """Build safe winws segments for ``all`` or ``lists`` mode.

    The return value contains complete segments, including their original
    ``--new`` separator when present.  An empty result in ``lists`` mode is
    intentional and means that no traffic should be intercepted.
    """

    if mode not in ("all", "lists"):
        raise ValueError(f"Unsupported traffic mode: {mode!r}")
    if isinstance(strategy_segments, str):
        raise TypeError("strategy_segments must be an iterable of segments, not a string")

    selection = (
        selected_lists
        if isinstance(selected_lists, UserListSelection)
        else UserListSelection.from_mapping(selected_lists)
    )
    selected = _selected_paths(selection, base_dir=base_dir)
    result: list[str] = []

    for raw_segment in strategy_segments:
        tokens = _tokenize(str(raw_segment))
        if not tokens:
            continue
        if mode == "all":
            built = _normalized_all_segment(tokens, base_dir=base_dir)
            if built:
                result.append(built)
        else:
            result.extend(_lists_segments(tokens, selected))

    # A strategy's final line normally omits ``--new``.  A list-only segment
    # can nevertheless expand into two segments (one domain and one IP
    # segment), so add separators to every generated segment except the
    # command's final segment.  Existing separators are preserved.
    if mode == "lists":
        separated: list[str] = []
        for index, segment in enumerate(result):
            value = _without_trailing_separator(segment)
            if index < len(result) - 1:
                value = f"{value} --new"
            if value:
                separated.append(value)
        result = separated
    return tuple(result)


def build_winws_command(
    winws_path: os.PathLike[str] | str,
    strategy_segments: Iterable[str],
    *,
    mode: TrafficMode = "all",
    selected_lists: UserListSelection | Mapping[str, Iterable[os.PathLike[str] | str]] | None = None,
    base_dir: os.PathLike[str] | str | None = None,
) -> str:
    """Build a complete command line without performing any system changes."""

    executable = normalize_path(winws_path, base_dir=base_dir)
    segments = build_traffic_segments(
        strategy_segments,
        mode=mode,
        selected_lists=selected_lists,
        base_dir=base_dir,
    )
    if not segments:
        return ""
    return " ".join([_quote_path(executable), *segments]).strip()


__all__ = [
    "TrafficMode",
    "UserListSelection",
    "build_traffic_segments",
    "build_winws_command",
    "normalize_path",
]
