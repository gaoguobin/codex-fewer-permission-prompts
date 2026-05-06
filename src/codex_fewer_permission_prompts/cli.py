#!/usr/bin/env python3
"""Suggest safe Codex prefix_rule entries from local Codex session history."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


BEGIN = "# BEGIN codex-fewer-permission-prompts"
END = "# END codex-fewer-permission-prompts"
DEFAULT_MIN_COUNT = 2
MAX_COMMAND_DISPLAY = 180
SENSITIVE_HINTS = (
    ".env",
    "auth.json",
    "token",
    "secret",
    "credential",
    "password",
    "private",
    "id_rsa",
    "apikey",
    "api_key",
)
COMPLEX_MARKERS = (
    "&&",
    "||",
    ";",
    "|",
    ">",
    "<",
    "$",
    "`",
    "$(",
    "${",
    "*",
    "?",
)
SHELL_EXECUTABLE_RE = re.compile(r"(?:^|[\\/])(pwsh|powershell)(?:\.exe)?$", re.I)
SLASH_ALIASES = {"/fewer-permission-prompts", "/fewer-prompts", "/fpp"}


@dataclass(frozen=True)
class SourceFile:
    path: Path
    kind: str


@dataclass(frozen=True)
class CommandRecord:
    command: str
    source_kind: str
    source_path: Path


@dataclass(frozen=True)
class Classification:
    safe: bool
    reason: str
    prefix_tokens: tuple[str, ...] = ()
    family: str = ""


@dataclass(frozen=True)
class RuleCandidate:
    command: str
    count: int
    source_kinds: tuple[str, ...]
    pattern: tuple[str, ...]
    family: str
    reason: str
    match: tuple[str, ...]
    not_match: tuple[str, ...]


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def default_rules_file(home: Path) -> Path:
    return home / "rules" / "default.rules"


def compact_path(path: Path, home: Path | None = None) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    home = home or Path.home()
    try:
        return "~/" + str(resolved.relative_to(home.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def safe_display(command: str) -> str:
    command = re.sub(r"(?i)(sk-|api[_-]?key|token|password|secret)[^\s'\"]*", r"\1<redacted>", command)
    command = command.replace(str(Path.home()), "~")
    command = re.sub(r"\s+", " ", command).strip()
    if len(command) <= MAX_COMMAND_DISPLAY:
        return command
    return command[: MAX_COMMAND_DISPLAY - 3] + "..."


def is_jsonl(path: Path) -> bool:
    return path.suffix.lower() == ".jsonl"


def iter_source_files(home: Path, limit_files: int = 200) -> list[SourceFile]:
    roots = [
        (home / "sessions", "codex_session"),
        (home / "history.jsonl", "codex_history"),
        (home / "log", "codex_log"),
    ]
    files: list[SourceFile] = []
    for root, kind in roots:
        if root.is_file() and is_jsonl(root):
            files.append(SourceFile(root, kind))
        elif root.is_dir():
            for path in root.rglob("*.jsonl"):
                if path.is_file():
                    files.append(SourceFile(path, kind))
    files.sort(key=lambda item: item.path.stat().st_mtime if item.path.exists() else 0, reverse=True)
    return files[:limit_files]


def read_jsonl(path: Path, max_lines: int | None = None) -> Iterator[dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if max_lines is not None and index >= max_lines:
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def summarize_shapes(home: Path, limit_files: int = 20, max_lines_per_file: int = 300) -> dict:
    shapes: Counter[str] = Counter()
    sources = iter_source_files(home, limit_files=limit_files)
    for source in sources:
        for value in read_jsonl(source.path, max_lines=max_lines_per_file):
            shape = json_shape(value)
            shapes[f"{source.kind}:{shape}"] += 1
    return {
        "source_files_checked": len(sources),
        "jsonl_shapes": [{"shape": key, "count": count} for key, count in shapes.most_common(25)],
    }


def json_shape(value: dict) -> str:
    top_type = str(value.get("type", ""))
    payload = value.get("payload")
    if isinstance(payload, dict):
        payload_type = str(payload.get("type", ""))
        name = str(payload.get("name", ""))
        if payload_type or name:
            return ",".join(part for part in (top_type, payload_type, name) if part)
    return top_type or ",".join(sorted(value.keys())[:5])


def extract_command_records(home: Path, limit_files: int = 200) -> list[CommandRecord]:
    records: list[CommandRecord] = []
    for source in iter_source_files(home, limit_files=limit_files):
        for value in read_jsonl(source.path):
            records.extend(extract_commands_from_event(value, source))
    return records


def extract_commands_from_event(value: dict, source: SourceFile) -> list[CommandRecord]:
    records: list[CommandRecord] = []
    if value.get("type") == "response_item":
        payload = value.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "function_call":
            if payload.get("name") == "shell_command":
                args = parse_arguments(payload.get("arguments"))
                command = args.get("command")
                if isinstance(command, str) and command.strip():
                    records.append(CommandRecord(command.strip(), source.kind, source.path))
    if value.get("type") == "event_msg":
        payload = value.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "exec_command_end":
            command = payload.get("command")
            if isinstance(command, str) and command.strip():
                records.append(CommandRecord(command.strip(), source.kind, source.path))
    return records


def parse_arguments(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
    return {}


def command_counts(records: Iterable[CommandRecord]) -> tuple[Counter[str], dict[str, set[str]]]:
    counts: Counter[str] = Counter()
    kinds: dict[str, set[str]] = defaultdict(set)
    for record in records:
        normalized = normalize_command(record.command)
        if not normalized:
            continue
        counts[normalized] += 1
        kinds[normalized].add(record.source_kind)
    return counts, kinds


def normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def split_command(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return []


def split_example_command(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def lower_tokens(tokens: Sequence[str]) -> list[str]:
    return [token.lower() for token in tokens]


def has_sensitive_hint(command: str) -> bool:
    lower = command.lower()
    return any(hint in lower for hint in SENSITIVE_HINTS)


def has_complex_shell(command: str) -> bool:
    return any(marker in command for marker in COMPLEX_MARKERS)


def classify(command: str) -> Classification:
    if has_sensitive_hint(command):
        return Classification(False, "contains sensitive path or secret hint")
    if has_complex_shell(command):
        return Classification(False, "contains shell metacharacters or expansion")

    tokens = split_command(command)
    if not tokens:
        return Classification(False, "cannot parse command safely")
    lowered = lower_tokens(tokens)
    first = lowered[0]

    if first in {"rm", "del", "erase", "rmdir", "remove-item", "move-item", "mv", "set-content", "add-content", "out-file", "new-item"}:
        return Classification(False, "destructive or writing command")
    if first in {"reg", "reg.exe", "icacls", "takeown", "sc", "sc.exe", "netsh", "set-acl", "start-service", "stop-service"}:
        return Classification(False, "system configuration command")
    if first in {"npm", "pnpm", "yarn"} and len(lowered) > 1 and lowered[1] in {"install", "i", "add"}:
        return Classification(False, "dependency installation command")
    if first in {"pip", "pip3"} and "install" in lowered[1:3]:
        return Classification(False, "dependency installation command")
    if first == "python" and lowered[1:4] == ["-m", "pip", "install"]:
        return Classification(False, "dependency installation command")

    if first == "git":
        return classify_git(tokens, lowered)
    if first in {"rg", "ripgrep"}:
        return Classification(True, "ripgrep is read-only search", (tokens[0],), "rg")
    if first in {"get-content", "type"}:
        return Classification(True, "PowerShell file read command", (tokens[0],), "powershell-read")
    if first in {"get-childitem", "dir", "ls", "gci"}:
        return Classification(True, "PowerShell directory listing command", (tokens[0],), "powershell-list")
    if lowered[:2] == ["codex", "--version"]:
        return Classification(True, "Codex version check", ("codex", "--version"), "codex-version")
    if lowered[:3] == ["codex", "mcp", "list"]:
        return Classification(True, "Codex MCP listing", ("codex", "mcp", "list"), "codex-mcp")
    if lowered[:4] == ["python", "-m", "codex_fast_proxy", "status"]:
        return Classification(True, "codex-fast-proxy status is diagnostic", ("python", "-m", "codex_fast_proxy", "status"), "fast-proxy")
    if lowered[:4] == ["python", "-m", "codex_fast_proxy", "doctor"]:
        return Classification(True, "codex-fast-proxy doctor is diagnostic", ("python", "-m", "codex_fast_proxy", "doctor"), "fast-proxy")

    return Classification(False, "not in the built-in low-risk allowlist")


def classify_git(tokens: Sequence[str], lowered: Sequence[str]) -> Classification:
    dangerous = {"reset", "checkout", "clean", "push", "commit", "add", "merge", "rebase", "switch", "restore"}
    if any(token in dangerous for token in lowered[1:]):
        return Classification(False, "git writing or history-changing command")

    index = 1
    prefix: list[str] = [tokens[0]]
    if len(tokens) >= 3 and tokens[1] == "-C":
        if has_sensitive_hint(tokens[2]):
            return Classification(False, "git -C path contains sensitive hint")
        prefix.extend([tokens[1], tokens[2]])
        index = 3
    elif len(tokens) >= 3 and lowered[1] == "-c":
        return Classification(False, "git config override is too broad for automatic recommendation")
    if index >= len(tokens):
        return Classification(False, "git subcommand missing")

    subcommand = lowered[index]
    if subcommand in {"status", "diff", "log"}:
        prefix.append(tokens[index])
        return Classification(True, f"git {subcommand} is read-only", tuple(prefix), f"git-{subcommand}")
    return Classification(False, "git subcommand is not in the low-risk allowlist")


def detect_powershell_wrapper(rules_file: Path | None = None) -> tuple[str, ...] | None:
    if rules_file and rules_file.exists():
        try:
            text = rules_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        wrappers: Counter[tuple[str, ...]] = Counter()
        for pattern in extract_pattern_lists(text):
            if len(pattern) >= 2 and SHELL_EXECUTABLE_RE.search(pattern[0]):
                if len(pattern) >= 3 and pattern[1].lower() == "-noprofile" and pattern[2].lower() == "-command":
                    wrappers[(pattern[0], pattern[1], pattern[2])] += 1
                elif pattern[1].lower() == "-command":
                    wrappers[(pattern[0], pattern[1])] += 1
        if wrappers:
            return wrappers.most_common(1)[0][0]
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if exe and os.name == "nt":
        return (exe, "-Command")
    return None


def extract_pattern_lists(text: str) -> Iterator[list[str]]:
    for match in re.finditer(r"pattern\s*=\s*(\[[^\n]*\])", text):
        try:
            value = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            yield value


def wrap_pattern(prefix_tokens: Sequence[str], command: str, mode: str, rules_file: Path | None) -> tuple[str, ...]:
    if mode == "none":
        return tuple(prefix_tokens)
    wrapper = detect_powershell_wrapper(rules_file)
    if mode == "powershell" or (mode == "auto" and wrapper):
        return tuple(wrapper) + (command,)
    return tuple(prefix_tokens)


def command_string_from_tokens(tokens: Sequence[str]) -> str:
    return shlex.join(list(tokens))


def build_match_examples(pattern: Sequence[str], family: str, command: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    match = (command_string_from_tokens(pattern),)
    if family.startswith("git-"):
        not_match = (command_string_from_tokens(replace_last(pattern, "commit")),)
    elif family == "rg":
        not_match = (command_string_from_tokens(replace_script(pattern, "grep pattern")),)
    elif family.startswith("powershell"):
        not_match = (command_string_from_tokens(replace_script(pattern, "Remove-Item sample.txt")),)
    elif family.startswith("codex"):
        not_match = (command_string_from_tokens(replace_last(pattern, "login")),)
    elif family == "fast-proxy":
        not_match = (command_string_from_tokens(replace_last(pattern, "install")),)
    else:
        not_match = (command_string_from_tokens(tuple(pattern) + ("danger",)),)
    return match, not_match


def replace_script(pattern: Sequence[str], script: str) -> tuple[str, ...]:
    if any(token.lower() == "-command" for token in pattern):
        tokens = list(pattern)
        tokens[-1] = script
        return tuple(tokens)
    return tuple(split_command(script))


def replace_last(pattern: Sequence[str], token: str) -> tuple[str, ...]:
    tokens = list(pattern)
    if tokens:
        tokens[-1] = token
    return tuple(tokens)


def propose_candidates(
    records: Iterable[CommandRecord],
    rules_file: Path | None,
    min_count: int,
    max_candidates: int,
    shell_wrapper: str,
) -> list[RuleCandidate]:
    counts, kinds = command_counts(records)
    candidates: list[RuleCandidate] = []
    seen_patterns: set[tuple[str, ...]] = set()
    for command, count in counts.most_common():
        if count < min_count:
            continue
        classification = classify(command)
        if not classification.safe:
            continue
        pattern = wrap_pattern(classification.prefix_tokens, command, shell_wrapper, rules_file)
        if pattern in seen_patterns:
            continue
        seen_patterns.add(pattern)
        match, not_match = build_match_examples(pattern, classification.family, command)
        candidates.append(
            RuleCandidate(
                command=command,
                count=count,
                source_kinds=tuple(sorted(kinds.get(command, set()))),
                pattern=pattern,
                family=classification.family,
                reason=classification.reason,
                match=match,
                not_match=not_match,
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def render_rule(candidate: RuleCandidate) -> str:
    return "\n".join(
        [
            "prefix_rule(",
            f"    pattern = {starlark_list(candidate.pattern)},",
            '    decision = "allow",',
            f"    justification = {json.dumps(candidate.reason)},",
            f"    match = {starlark_list(candidate.match)},",
            f"    not_match = {starlark_list(candidate.not_match)},",
            ")",
        ]
    )


def render_block(candidates: Sequence[RuleCandidate]) -> str:
    lines = [
        BEGIN,
        "# Generated by codex-fewer-permission-prompts.",
        "# Review each rule before keeping it. Rules are loaded on Codex startup.",
    ]
    for candidate in candidates:
        lines.append("")
        lines.append(f"# observed_count = {candidate.count}; command = {json.dumps(safe_display(candidate.command))}")
        lines.append(render_rule(candidate))
    lines.append(END)
    return "\n".join(lines) + "\n"


def starlark_list(values: Sequence[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def strip_sentinel(text: str) -> tuple[str, bool]:
    pattern = re.compile(rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?", re.S)
    new_text, count = pattern.subn("\n", text)
    return new_text.rstrip() + ("\n" if new_text.strip() else ""), count > 0


def replace_sentinel(text: str, block: str) -> str:
    stripped, _ = strip_sentinel(text)
    if stripped and not stripped.endswith("\n"):
        stripped += "\n"
    if stripped:
        stripped += "\n"
    return stripped + block


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + f".bak.{timestamp()}")
    if path.exists():
        shutil.copy2(path, backup)
    else:
        backup.write_text("", encoding="utf-8")
    return backup


def latest_backup(path: Path) -> Path | None:
    backups = sorted(path.parent.glob(path.name + ".bak.*"), key=lambda item: item.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def cmd_doctor(args: argparse.Namespace) -> int:
    home = Path(args.codex_home).expanduser() if args.codex_home else codex_home()
    rules = Path(args.rules_file).expanduser() if args.rules_file else default_rules_file(home)
    rules_dir = rules.parent
    data = {
        "codex_home": str(home),
        "codex_home_exists": home.exists(),
        "rules_dir": str(rules_dir),
        "rules_dir_exists": rules_dir.exists(),
        "rules_file": str(rules),
        "rules_file_exists": rules.exists(),
        "rules_file_has_sentinel": rules.exists() and BEGIN in rules.read_text(encoding="utf-8", errors="replace"),
        "sessions_dir_exists": (home / "sessions").exists(),
        "history_file_exists": (home / "history.jsonl").exists(),
        "log_dir_exists": (home / "log").exists(),
    }
    data.update(summarize_shapes(home, limit_files=args.limit_files))
    if args.json:
        print_json(data)
    else:
        for key, value in data.items():
            if key == "jsonl_shapes":
                print("jsonl_shapes:")
                for item in value:
                    print(f"  {item['count']:>5} {item['shape']}")
            else:
                print(f"{key}: {value}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    home = Path(args.codex_home).expanduser() if args.codex_home else codex_home()
    records = extract_command_records(home, limit_files=args.limit_files)
    counts, kinds = command_counts(records)
    rows = []
    for command, count in counts.most_common(args.max_rows):
        rows.append(
            {
                "count": count,
                "command": safe_display(command),
                "source_kinds": sorted(kinds.get(command, set())),
                "classification": classify(command).reason,
                "recommended": classify(command).safe and count >= args.min_count,
            }
        )
    if args.json:
        print_json({"commands_seen": len(counts), "rows": rows})
    else:
        print(f"commands_seen: {len(counts)}")
        for row in rows:
            marker = "candidate" if row["recommended"] else "skip"
            print(f"{row['count']:>5} {marker:<9} {row['command']} ({row['classification']})")
    return 0


def load_or_generate_candidates(args: argparse.Namespace) -> list[RuleCandidate]:
    if getattr(args, "proposal_json", None):
        return candidates_from_json(Path(args.proposal_json).expanduser())
    home = Path(args.codex_home).expanduser() if getattr(args, "codex_home", None) else codex_home()
    rules = Path(args.rules_file).expanduser() if getattr(args, "rules_file", None) else default_rules_file(home)
    records = extract_command_records(home, limit_files=getattr(args, "limit_files", 200))
    return propose_candidates(records, rules, args.min_count, args.max_candidates, args.shell_wrapper)


def cmd_propose(args: argparse.Namespace) -> int:
    candidates = load_or_generate_candidates(args)
    if getattr(args, "json", False):
        print_json({"candidates": [candidate_to_json(item) for item in candidates]})
        return 0
    if not candidates:
        print("No safe candidates met the current threshold.")
        return 0
    print(render_block(candidates), end="")
    return 0


def cmd_default(args: argparse.Namespace) -> int:
    print("== doctor ==")
    doctor_args = argparse.Namespace(codex_home=args.codex_home, rules_file=args.rules_file, limit_files=args.limit_files, json=False)
    status = cmd_doctor(doctor_args)
    if status:
        return status
    print("\n== propose (dry-run) ==")
    return cmd_propose(args)


def candidate_to_json(candidate: RuleCandidate) -> dict:
    return {
        "command": candidate.command,
        "count": candidate.count,
        "source_kinds": list(candidate.source_kinds),
        "pattern": list(candidate.pattern),
        "family": candidate.family,
        "reason": candidate.reason,
        "match": list(candidate.match),
        "not_match": list(candidate.not_match),
    }


def candidates_from_json(path: Path) -> list[RuleCandidate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_candidates = data.get("candidates", data if isinstance(data, list) else [])
    candidates: list[RuleCandidate] = []
    for item in raw_candidates:
        candidates.append(
            RuleCandidate(
                command=str(item["command"]),
                count=int(item.get("count", 0)),
                source_kinds=tuple(item.get("source_kinds", [])),
                pattern=tuple(item["pattern"]),
                family=str(item.get("family", "")),
                reason=str(item.get("reason", "")),
                match=tuple(item.get("match", [])),
                not_match=tuple(item.get("not_match", [])),
            )
        )
    return candidates


def extract_candidates_from_rules(path: Path) -> list[RuleCandidate]:
    text = path.read_text(encoding="utf-8", errors="replace")
    block_text, found = sentinel_text(text)
    if not found:
        block_text = text
    candidates: list[RuleCandidate] = []
    for match in re.finditer(r"prefix_rule\((.*?)\)", block_text, re.S):
        body = match.group(1)
        pattern = extract_list_field(body, "pattern")
        matches = extract_list_field(body, "match")
        not_matches = extract_list_field(body, "not_match")
        if not pattern or not matches or not not_matches:
            continue
        candidates.append(
            RuleCandidate(
                command=matches[0],
                count=0,
                source_kinds=(),
                pattern=tuple(pattern),
                family="existing",
                reason="existing rule",
                match=tuple(matches),
                not_match=tuple(not_matches),
            )
        )
    return candidates


def sentinel_text(text: str) -> tuple[str, bool]:
    match = re.search(rf"{re.escape(BEGIN)}.*?{re.escape(END)}", text, re.S)
    return (match.group(0), True) if match else ("", False)


def extract_list_field(body: str, field: str) -> list[str]:
    match = re.search(rf"{field}\s*=\s*(\[[^\]]*\])", body, re.S)
    if not match:
        return []
    try:
        value = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def cmd_verify(args: argparse.Namespace) -> int:
    if args.proposal_json:
        proposal_path = Path(args.proposal_json).expanduser()
        candidates = candidates_from_json(proposal_path)
        if args.rules_file:
            rules = Path(args.rules_file).expanduser()
            return verify_candidates(rules, candidates, args.verbose)
        rules = temporary_rules_path(proposal_path)
        try:
            rules.write_text(render_block(candidates), encoding="utf-8")
            return verify_candidates(rules, candidates, args.verbose)
        finally:
            try:
                rules.unlink()
            except FileNotFoundError:
                pass
    if not args.rules_file:
        print("Provide --rules-file, or pass --proposal-json to verify a dry-run proposal.", file=sys.stderr)
        return 2
    rules = Path(args.rules_file).expanduser()
    candidates = extract_candidates_from_rules(rules)
    return verify_candidates(rules, candidates, args.verbose)


def temporary_rules_path(proposal_path: Path) -> Path:
    parent = proposal_path.parent if str(proposal_path.parent) else Path(".")
    stem = proposal_path.name
    for index in range(100):
        suffix = f".verify.{os.getpid()}.{index}.rules"
        candidate = parent / f"{stem}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate temporary rules file next to {proposal_path}")


def verify_candidates(rules: Path, candidates: list[RuleCandidate], verbose: bool) -> int:
    if not candidates:
        print("No verifiable rules found. Provide --proposal-json or a rules file with match/not_match examples.")
        return 1
    failures = 0
    for candidate in candidates:
        for example in candidate.match:
            ok, output = execpolicy_check(rules, example, should_match=True)
            print(f"match     {'ok' if ok else 'FAIL'}  {safe_display(example)}")
            if not ok:
                failures += 1
                if verbose:
                    print(output)
        for example in candidate.not_match:
            ok, output = execpolicy_check(rules, example, should_match=False)
            print(f"not_match {'ok' if ok else 'FAIL'}  {safe_display(example)}")
            if not ok:
                failures += 1
                if verbose:
                    print(output)
    return 1 if failures else 0


def execpolicy_check(rules: Path, command: str, should_match: bool) -> tuple[bool, str]:
    tokens = split_example_command(command)
    if not tokens:
        return False, "could not parse example command"
    proc = subprocess.run(
        ["codex", "execpolicy", "check", "--pretty", "--rules", str(rules), "--", *tokens],
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, output
    matched = bool(data.get("matchedRules"))
    decision = data.get("decision")
    if should_match:
        return proc.returncode == 0 and matched and decision == "allow", output
    return proc.returncode == 0 and not matched, output


def cmd_apply(args: argparse.Namespace) -> int:
    rules = Path(args.rules_file).expanduser()
    candidates = load_or_generate_candidates(args)
    if not candidates:
        print("No safe candidates to apply.")
        return 0
    old = rules.read_text(encoding="utf-8", errors="replace") if rules.exists() else ""
    new = replace_sentinel(old, render_block(candidates))
    diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=str(rules), tofile=str(rules) + " (new)", lineterm=""))
    print(diff if diff else "No changes.")
    if not args.write and not args.yes:
        print("Dry-run only. Re-run with --write to apply, or --yes for non-interactive apply.")
        return 0
    if not args.yes and not confirm("Apply these rules?"):
        print("Aborted.")
        return 1
    backup = backup_file(rules)
    rules.write_text(new, encoding="utf-8")
    print(f"Backup: {backup}")
    print(f"Updated: {rules}")
    return 0


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} Type 'yes' to continue: ").strip().lower()
    return answer == "yes"


def cmd_rollback(args: argparse.Namespace) -> int:
    rules = Path(args.rules_file).expanduser()
    if args.backup:
        source = Path(args.backup).expanduser()
        if not source.exists():
            print(f"Backup not found: {source}", file=sys.stderr)
            return 1
        if not args.yes and not confirm(f"Restore backup {source} to {rules}?"):
            print("Aborted.")
            return 1
        shutil.copy2(source, rules)
        print(f"Restored: {rules}")
        return 0

    if args.remove_block:
        old = rules.read_text(encoding="utf-8", errors="replace") if rules.exists() else ""
        new, removed = strip_sentinel(old)
        if not removed:
            print("No sentinel block found.")
            return 0
        diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=str(rules), tofile=str(rules) + " (rollback)", lineterm=""))
        print(diff)
        if not args.yes and not confirm("Remove sentinel block?"):
            print("Aborted.")
            return 1
        backup = backup_file(rules)
        rules.write_text(new, encoding="utf-8")
        print(f"Backup: {backup}")
        print(f"Removed sentinel block from: {rules}")
        return 0

    source = latest_backup(rules)
    if not source:
        print("No backup found. Use --remove-block to remove only the sentinel block.", file=sys.stderr)
        return 1
    if not args.yes and not confirm(f"Restore latest backup {source} to {rules}?"):
        print("Aborted.")
        return 1
    shutil.copy2(source, rules)
    print(f"Restored latest backup: {source}")
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codex-home", help="Override CODEX_HOME. Defaults to CODEX_HOME or ~/.codex.")
    parser.add_argument("--rules-file", help="Rules file path. Defaults to CODEX_HOME/rules/default.rules.")
    parser.add_argument("--limit-files", type=int, default=200, help="Maximum JSONL files to inspect.")


def add_proposal_args(parser: argparse.ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--shell-wrapper", choices=("auto", "none", "powershell"), default="auto")
    parser.add_argument("--proposal-json", help="Use candidates from a JSON proposal instead of scanning history.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    default = sub.add_parser("default", help="Run the default dry-run workflow: doctor, then propose.")
    add_proposal_args(default)
    default.set_defaults(func=cmd_default)

    doctor = sub.add_parser("doctor", help="Inspect Codex paths and JSONL shapes without content.")
    add_common_args(doctor)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    status = sub.add_parser("status", help="Alias for doctor; inspect current rules and scan inputs.")
    add_common_args(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_doctor)

    analyze = sub.add_parser("analyze", help="Count observed shell commands.")
    add_common_args(analyze)
    analyze.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT)
    analyze.add_argument("--max-rows", type=int, default=50)
    analyze.add_argument("--json", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    scan = sub.add_parser("scan", help="Alias for analyze; count observed shell commands.")
    add_common_args(scan)
    scan.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT)
    scan.add_argument("--max-rows", type=int, default=50)
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=cmd_analyze)

    propose = sub.add_parser("propose", help="Print candidate prefix_rule entries.")
    add_proposal_args(propose)
    propose.add_argument("--dry-run", action="store_true", help="Accepted for workflow clarity; propose never writes files.")
    propose.add_argument("--json", action="store_true")
    propose.set_defaults(func=cmd_propose)

    verify = sub.add_parser("verify", help="Verify rules with codex execpolicy check.")
    verify.add_argument("--rules-file")
    verify.add_argument("--proposal-json")
    verify.add_argument("--verbose", action="store_true")
    verify.set_defaults(func=cmd_verify)

    apply = sub.add_parser("apply", help="Apply candidate rules to a rules file.")
    add_proposal_args(apply)
    apply.add_argument("--write", action="store_true", help="Actually write the rules file after showing the diff.")
    apply.add_argument("--dry-run", action="store_true", help="Deprecated no-op; apply is dry-run unless --write or --yes is set.")
    apply.add_argument("--yes", action="store_true", help="Apply without interactive confirmation.")
    apply.set_defaults(func=cmd_apply)

    rollback = sub.add_parser("rollback", help="Restore a backup or remove the sentinel block.")
    rollback.add_argument("--rules-file", required=True)
    rollback.add_argument("--backup")
    rollback.add_argument("--remove-block", action="store_true")
    rollback.add_argument("--yes", action="store_true")
    rollback.set_defaults(func=cmd_rollback)

    return parser


def normalize_argv(argv: Sequence[str] | None) -> list[str] | None:
    if argv is None:
        raw = sys.argv[1:]
    else:
        raw = list(argv)
    if raw and raw[0].lower() in SLASH_ALIASES:
        raw = raw[1:] or ["default"]
    if not raw:
        raw = ["default"]
    return raw


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
