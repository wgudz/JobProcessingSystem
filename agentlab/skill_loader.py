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

SKILL_REFERENCE_FILES = (
    'references/architecture.md',
    'references/triage.md'
)


def load_skill_references(
    skills_root: Path,
    name: str
) -> str:

    if not name or any(
        x in name
        for x in ('/', '\\', '..')
    ):
        raise ValueError(
            'Invalid skill name'
        )

    root = skills_root.resolve(
        strict=True
    )

    skill_dir = (
        root
        / name
    ).resolve(strict=True)

    if not skill_dir.is_relative_to(root):
        raise ValueError(
            'Skill outside skills directory'
        )

    parts = []

    for relative in SKILL_REFERENCE_FILES:
        path = skill_dir / relative

        cursor = skill_dir

        for component in Path(relative).parts:
            cursor = cursor / component

            if cursor.is_symlink():
                raise ValueError(
                    'Skill reference cannot be a symlink'
                )

        if (
            not path.is_file()
            or not path.resolve().is_relative_to(skill_dir)
        ):
            raise FileNotFoundError(
                f'Missing Skill reference: {relative}'
            )

        content = path.read_text(
            encoding='utf-8'
        )

        parts.append(
            f'## {relative}\n\n'
            + content[:12000]
        )

    return '\n\n'.join(parts)
