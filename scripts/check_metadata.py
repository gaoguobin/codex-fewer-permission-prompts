#!/usr/bin/env python3
"""Validate repository metadata for skill and plugin discovery."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11 in CI.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "codex-fewer-permission-prompts"
PLUGIN_NAME = "codex-permission-tools"
LEGACY_NAMESPACE = "codex-permission-tools"
SKILL_PATH = Path("skills") / SKILL_NAME / "SKILL.md"
DIRECT_SKILL_LINK = f".agents/skills/{SKILL_NAME}"
STANDALONE_SKILL_MIRROR = f".codex/{SKILL_NAME}-skill/{SKILL_NAME}"


def fail(message: str) -> None:
    print(f"metadata check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail(f"{path} is missing YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            fail(f"{path} has invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def anchor_for(heading: str) -> str:
    anchor = re.sub(r"[^a-z0-9 -]", "", heading.lower()).strip().replace(" ", "-")
    return re.sub(r"-+", "-", anchor)


def title_from_kebab(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-") if part)


def check_readme() -> None:
    path = ROOT / "README.md"
    if not path.exists():
        fail("README.md is missing")
    text = path.read_text(encoding="utf-8")
    required = [
        "Agent Skill and Discovery",
        f"`{SKILL_NAME}`",
        f"`{SKILL_PATH.as_posix()}`",
        "Plugin Readiness",
        "Safety Model",
        "SkillsMP",
        f"`{PLUGIN_NAME}`",
        f"`~/{DIRECT_SKILL_LINK}`",
        f"`~/{STANDALONE_SKILL_MIRROR}`",
        "standalone skill mirror",
        "plugin namespace prefix",
        "open a new conversation",
        "旧 thread",
        "not an official OpenAI plugin",
    ]
    for snippet in required:
        if snippet not in text:
            fail(f"README.md is missing required discovery text: {snippet}")

    anchors = {"chinese"}
    for line in text.splitlines():
        match = re.match(r"^(#+)\s+(.+?)\s*$", line)
        if match:
            anchors.add(anchor_for(match.group(2)))

    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if link.startswith("#") and link[1:] not in anchors:
            fail(f"README.md has broken anchor: {link}")


def check_skills() -> None:
    root_skill = ROOT / "SKILL.md"
    bundled_skill = ROOT / SKILL_PATH
    if root_skill.read_text(encoding="utf-8") != bundled_skill.read_text(encoding="utf-8"):
        fail("root SKILL.md and bundled skill SKILL.md differ")

    for path in (root_skill, bundled_skill):
        fields = parse_frontmatter(path)
        if set(fields) != {"name", "description"}:
            fail(f"{path} frontmatter must contain only name and description")
        if fields["name"] != SKILL_NAME:
            fail(f"{path} has unexpected skill name: {fields['name']}")
        if len(fields["description"]) > 300:
            fail(f"{path} description is too long for skill indexes")
        for token in ("Codex", "permission prompts", "prefix_rule", "execpolicy"):
            if token not in fields["description"]:
                fail(f"{path} description is missing search token: {token}")


def check_plugin_manifest() -> None:
    path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME:
        fail("plugin manifest name must be the stable plugin namespace")
    if manifest.get("skills") != "./skills/":
        fail("plugin manifest skills path must be ./skills/")
    keywords = set(manifest.get("keywords", []))
    for keyword in ("agent-skills", "codex-plugin", "skillsmp", "prefix-rule"):
        if keyword not in keywords:
            fail(f"plugin manifest missing keyword: {keyword}")
    interface = manifest.get("interface", {})
    if not interface.get("displayName") or not interface.get("shortDescription"):
        fail("plugin manifest interface metadata is incomplete")
    if interface.get("displayName") == title_from_kebab(SKILL_NAME):
        fail("plugin displayName duplicates the skill title in Codex skill menus")


def check_codex_docs() -> None:
    docs = {
        "INSTALL.md": ROOT / ".codex" / "INSTALL.md",
        "UPDATE.md": ROOT / ".codex" / "UPDATE.md",
        "UNINSTALL.md": ROOT / ".codex" / "UNINSTALL.md",
    }
    for name, path in docs.items():
        text = path.read_text(encoding="utf-8")
        if ".agents\\skills" not in text or SKILL_NAME not in text:
            fail(f".codex/{name} does not mention the user skill junction")
        if "codex-fewer-permission-prompts-skill" not in text:
            fail(f".codex/{name} does not mention the standalone skill mirror")
    for name in ("INSTALL.md", "UPDATE.md"):
        text = docs[name].read_text(encoding="utf-8")
        if "旧 thread" not in text or "新开一个对话" not in text:
            fail(f".codex/{name} must warn that existing threads may cache skill menus")
        if "skillMirror" not in text:
            fail(f".codex/{name} must create or refresh the standalone skill mirror")
    update_text = docs["UPDATE.md"].read_text(encoding="utf-8")
    uninstall_text = docs["UNINSTALL.md"].read_text(encoding="utf-8")
    for name, text in (("UPDATE.md", update_text), ("UNINSTALL.md", uninstall_text)):
        if LEGACY_NAMESPACE not in text or "legacyParentTarget" not in text or "legacyInnerTarget" not in text:
            fail(f".codex/{name} must handle legacy namespace-style junctions")


def check_pyproject() -> None:
    path = ROOT / "pyproject.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    if project.get("readme") != "README.md":
        fail("pyproject readme must point to README.md")
    keywords = set(project.get("keywords", []))
    for keyword in ("agent-skill", "codex-plugin", "skillsmp", "prefix-rule"):
        if keyword not in keywords:
            fail(f"pyproject missing keyword: {keyword}")
    urls = project.get("urls", {})
    for key in ("Homepage", "Repository", "Issues", "Documentation"):
        if key not in urls:
            fail(f"pyproject missing project.urls.{key}")


def main() -> int:
    check_readme()
    check_skills()
    check_plugin_manifest()
    check_codex_docs()
    check_pyproject()
    print("metadata-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
