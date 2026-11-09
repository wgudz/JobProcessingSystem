"""Read a Skill's entry point as plain instructions (no code execution)."""
from pathlib import Path


def load_skill(skills_root: Path, name: str) -> str:
    if not name or any(x in name for x in ("/", "\\", "..")):
        raise ValueError("Invalid skill name")
    root = skills_root.resolve()
    entry = root / name / "SKILL.md"
    if entry.is_symlink() or not entry.is_file() or not entry.resolve().is_relative_to(root):
        raise FileNotFoundError(f"Skill not found: {name}")
    content = entry.read_text(encoding="utf-8")
    if not content.startswith("---\n") or "\n---\n" not in content[4:]:
        raise ValueError("Invalid SKILL.md: YAML frontmatter is missing")
    if "name:" not in content.split("---", 2)[1]:
        raise ValueError("Invalid SKILL.md: name is missing")
    return content[:22000]
