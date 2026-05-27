"""Filesystem bootstrap for baoyu-slide-deck (analysis.md, source.md)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

EXTEND_MD = """\
# Slide Deck Preferences (SDK bootstrap)

## Defaults
style: blueprint
audience: general
language: zh
review: false
"""

IMAGE_GEN_EXTEND_MD = """\
---
version: 1
default_provider: google
default_quality: 2k
default_aspect_ratio: "16:9"
---
"""

SLIDE_IMAGE_NAME_RE = re.compile(r"^\d{2}-slide-.+\.png$", re.IGNORECASE)

STYLE_SIGNAL_RULES: tuple[tuple[str, str], ...] = (
    ("tutorial|learn|education|guide|beginner", "sketch-notes"),
    ("classroom|teaching|school|chalkboard", "chalkboard"),
    ("architecture|system|data|analysis|technical", "blueprint"),
    ("executive|minimal|clean|simple", "minimal"),
    ("saas|product|dashboard|metrics", "notion"),
    ("investor|quarterly|business|corporate", "corporate"),
    ("launch|marketing|keynote", "bold-editorial"),
)

SLIDE_DECK_SKILL_RE = re.compile(
    r"(?:/skill:)?baoyu-slide-deck\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkspaceBootstrap:
    content_path: Path
    topic_slug: str
    topic_dir: Path
    analysis_path: Path


@dataclass(frozen=True)
class BootstrapOptions:
    lang: str = "zh"
    slides: int = 6
    audience: str = "general"
    style: str | None = None
    force: bool = False


def is_slide_deck_prompt(prompt: str) -> bool:
    return bool(SLIDE_DECK_SKILL_RE.search(prompt))


def parse_content_path_from_prompt(prompt: str, *, default: str = "content.md") -> str:
    for token in prompt.split():
        if token.endswith(".md") and not token.startswith("-"):
            return token
    return default


def parse_int_flag(prompt: str, flag: str, default: int) -> int:
    match = re.search(rf"{re.escape(flag)}\s+(\d+)", prompt)
    if not match:
        return default
    return int(match.group(1))


def parse_lang_from_prompt(prompt: str, default: str) -> str:
    match = re.search(r"--lang\s+(\S+)", prompt)
    if match:
        return match.group(1)
    return default


def _slugify_title(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    if words:
        return "-".join(words[:4])
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
    return f"deck-{digest}"


def derive_topic_slug(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            title = re.sub(r"^#+\s*", "", stripped).strip()
            if title:
                return _slugify_title(title)
        return _slugify_title(stripped)
    return "slide-deck-topic"


def list_topic_dirs(workspace: Path) -> list[Path]:
    """Topic dirs under slide-deck/, newest activity first."""
    deck_root = workspace / "slide-deck"
    if not deck_root.is_dir():
        return []
    dirs = [child for child in deck_root.iterdir() if child.is_dir()]
    return sorted(
        dirs,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _topic_dirs_with_artifact(
    workspace: Path,
    artifact: str,
) -> list[Path]:
    return [
        topic_dir
        for topic_dir in list_topic_dirs(workspace)
        if (topic_dir / artifact).is_file()
    ]


def resolve_topic_dir(
    workspace: Path,
    bootstrap: WorkspaceBootstrap,
    *,
    prefer_artifact: str | None = None,
    prefer_artifacts: tuple[str, ...] | None = None,
) -> Path:
    """Return topic dir where deck artifacts actually live.

    The agent may choose a slug that differs from ``derive_topic_slug()``.
    When ``prefer_artifact`` / ``prefer_artifacts`` is set, prefer the newest
    topic directory that contains that file (first match wins).
    """
    artifacts: tuple[str, ...] = ()
    if prefer_artifacts is not None:
        artifacts = prefer_artifacts
    elif prefer_artifact is not None:
        artifacts = (prefer_artifact,)
    expected = bootstrap.topic_dir
    for artifact in artifacts:
        if (expected / artifact).is_file():
            return expected
        matches = _topic_dirs_with_artifact(workspace, artifact)
        if matches:
            return matches[0]
    return expected


def list_slide_images(topic_dir: Path) -> list[Path]:
    """Slide PNGs in a topic dir (``01-slide-cover.png``, etc.)."""
    if not topic_dir.is_dir():
        return []
    return sorted(
        path
        for path in topic_dir.iterdir()
        if path.is_file() and SLIDE_IMAGE_NAME_RE.match(path.name)
    )


def analysis_step2_complete(text: str) -> bool:
    """True when analysis.md reflects completed Step 2 (SDK or skill format)."""
    if "step_2_complete: true" in text:
        return True
    return "## Confirmed Preferences" in text


def detect_content_signals(content: str) -> list[str]:
    lowered = content.lower()
    hits: list[str] = []
    patterns = (
        ("tutorial", r"\b(tutorial|learn|education|guide|beginner)\b"),
        ("technical", r"\b(architecture|system|api|sdk|agent)\b"),
        ("executive", r"\b(executive|strategy|roi|business)\b"),
        ("product", r"\b(product|saas|dashboard)\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, lowered):
            hits.append(label)
    return hits or ["general"]


def recommend_style(signals: list[str], content: str) -> str:
    lowered = content.lower()
    for pattern, preset in STYLE_SIGNAL_RULES:
        if re.search(pattern, lowered):
            return preset
    if "technical" in signals:
        return "blueprint"
    if "tutorial" in signals:
        return "sketch-notes"
    return "blueprint"


def estimate_slide_count(content: str, target: int) -> int:
    words = len(re.findall(r"\S+", content))
    if words < 1000:
        suggested = max(5, min(10, target))
    elif words < 3000:
        suggested = max(10, min(18, target))
    elif words < 5000:
        suggested = max(15, min(25, target))
    else:
        suggested = max(20, min(30, target))
    return max(5, min(30, target if target else suggested))


def read_extend_defaults(workspace: Path) -> dict[str, str]:
    extend = workspace / ".baoyu-skills" / "baoyu-slide-deck" / "EXTEND.md"
    defaults = {
        "style": "blueprint",
        "audience": "general",
        "language": "zh",
        "review": "false",
    }
    if not extend.is_file():
        return defaults
    text = extend.read_text(encoding="utf-8")
    for key in defaults:
        match = re.search(rf"^{key}:\s*(\S+)", text, re.MULTILINE)
        if match:
            defaults[key] = match.group(1)
    return defaults


def build_analysis_markdown(
    *,
    topic: str,
    topic_slug: str,
    audience: str,
    language: str,
    style: str,
    slide_count: int,
    signals: list[str],
    word_count: int,
    skip_outline_review: bool,
    skip_prompt_review: bool,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    skip_outline = "true" if skip_outline_review else "false"
    skip_prompts = "true" if skip_prompt_review else "false"
    signal_lines = "\n".join(f"- {item}" for item in signals)
    return f"""\
# Slide Deck Analysis

sdk_bootstrap: true
generated_at: {now}
step_2_complete: true

## Topic

{topic}

**Topic slug**: `{topic_slug}`

## Audience

{audience}

## Content signals

{signal_lines}

## Recommendations (Step 1)

| Field | Value |
|-------|-------|
| Style | {style} |
| Slide count | {slide_count} |
| Language | {language} |
| Source word count | {word_count} |

## Confirmed preferences (Step 2 — SDK defaults)

| Field | Value |
|-------|-------|
| style | {style} |
| audience | {audience} |
| language | {language} |
| slide_count | {slide_count} |
| skip_outline_review | {skip_outline} |
| skip_prompt_review | {skip_prompts} |

## Next step

Proceed to **Step 3: Generate Outline** using the confirmed style and slide
count above. Source material is in ``source.md`` in this directory.
"""


def ensure_extend_md(workspace: Path) -> None:
    extend_dir = workspace / ".baoyu-skills" / "baoyu-slide-deck"
    extend_dir.mkdir(parents=True, exist_ok=True)
    extend_file = extend_dir / "EXTEND.md"
    if not extend_file.is_file():
        extend_file.write_text(EXTEND_MD, encoding="utf-8")
    (workspace / "slide-deck").mkdir(parents=True, exist_ok=True)


def ensure_image_gen_extend_md(workspace: Path) -> None:
    """Project EXTEND for baoyu-image-gen (non-interactive SDK full runs)."""
    extend_dir = workspace / ".baoyu-skills" / "baoyu-image-gen"
    extend_dir.mkdir(parents=True, exist_ok=True)
    project_extend = extend_dir / "EXTEND.md"
    if project_extend.is_file():
        return
    user_extend = (
        Path.home() / ".baoyu-skills" / "baoyu-image-gen" / "EXTEND.md"
    )
    if user_extend.is_file():
        project_extend.write_text(
            user_extend.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    else:
        project_extend.write_text(IMAGE_GEN_EXTEND_MD, encoding="utf-8")


def ensure_content_md(workspace: Path, content_src: Path) -> Path:
    if not content_src.is_file():
        msg = f"Content file not found: {content_src}"
        raise FileNotFoundError(msg)
    content_dest = workspace / "content.md"
    content_dest.write_text(
        content_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return content_dest


def ensure_analysis_md(
    workspace: Path,
    content_text: str,
    options: BootstrapOptions | None = None,
) -> WorkspaceBootstrap:
    """Write slide-deck/{{slug}}/analysis.md and source.md."""
    opts = options or BootstrapOptions()
    workspace.mkdir(parents=True, exist_ok=True)
    extend = read_extend_defaults(workspace)
    language = opts.lang or extend["language"]
    audience = opts.audience or extend["audience"]
    review_enabled = extend["review"].lower() in {"true", "yes", "1"}
    skip_outline_review = not review_enabled
    skip_prompt_review = not review_enabled

    topic_slug = derive_topic_slug(content_text)
    topic_dir = workspace / "slide-deck" / topic_slug
    topic_dir.mkdir(parents=True, exist_ok=True)

    source_path = topic_dir / "source.md"
    source_path.write_text(content_text, encoding="utf-8")

    analysis_path = topic_dir / "analysis.md"
    if analysis_path.is_file() and not opts.force:
        return WorkspaceBootstrap(
            content_path=workspace / "content.md",
            topic_slug=topic_slug,
            topic_dir=topic_dir,
            analysis_path=analysis_path,
        )

    signals = detect_content_signals(content_text)
    resolved_style = opts.style or extend["style"] or recommend_style(
        signals,
        content_text,
    )
    slide_count = estimate_slide_count(content_text, opts.slides)
    topic = topic_slug.replace("-", " ").title()
    for line in content_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            topic = re.sub(r"^#+\s*", "", stripped).strip() or topic
            break

    word_count = len(re.findall(r"\S+", content_text))
    analysis_path.write_text(
        build_analysis_markdown(
            topic=topic,
            topic_slug=topic_slug,
            audience=audience,
            language=language,
            style=resolved_style,
            slide_count=slide_count,
            signals=signals,
            word_count=word_count,
            skip_outline_review=skip_outline_review,
            skip_prompt_review=skip_prompt_review,
        ),
        encoding="utf-8",
    )
    return WorkspaceBootstrap(
        content_path=workspace / "content.md",
        topic_slug=topic_slug,
        topic_dir=topic_dir,
        analysis_path=analysis_path,
    )


def bootstrap_from_prompt(
    workspace: Path,
    prompt: str,
    options: BootstrapOptions | None = None,
) -> WorkspaceBootstrap | None:
    """Ensure analysis.md when prompt targets baoyu-slide-deck."""
    if not is_slide_deck_prompt(prompt):
        return None
    opts = options or BootstrapOptions()
    content_name = parse_content_path_from_prompt(prompt)
    content_path = workspace / content_name
    if not content_path.is_file():
        return None
    content_text = content_path.read_text(encoding="utf-8")
    merged = BootstrapOptions(
        lang=parse_lang_from_prompt(prompt, opts.lang),
        slides=parse_int_flag(prompt, "--slides", opts.slides),
        audience=opts.audience,
        style=opts.style,
        force=opts.force,
    )
    return ensure_analysis_md(workspace, content_text, merged)


def build_runbook_appendix(
    bootstrap: WorkspaceBootstrap,
    *,
    full_pipeline: bool = False,
    slide_count: int = 6,
) -> str:
    analysis_rel = bootstrap.analysis_path.relative_to(
        bootstrap.content_path.parent,
    )
    base = f"""

## SDK slide-deck guard (extension)

Non-interactive run. Do not use AskUserQuestion.

- Analysis: `{analysis_rel}` (`step_2_complete: true`)
- Topic dir: `slide-deck/{bootstrap.topic_slug}/` (agent may pick another slug)
- Start at **Step 3 (Generate Outline)**; do not redo Steps 1–2.
- Read `source.md` in the topic directory before writing `outline.md`.
"""
    if not full_pipeline:
        return base
    return base + f"""
- **Full pipeline (SDK)**: finish Steps 3–9 in this session without stopping
  at outline.
- After prompts, generate each slide image via **`/skill:baoyu-image-gen`**
  (already loaded in this SDK session). Do **not** call provider HTTP APIs
  directly; use only that skill's scripts.
- Write PNGs beside `outline.md` in the topic dir (`01-slide-cover.png`, …).
- Target slide count: **{slide_count}** (from `--slides`).
- Merge PPTX/PDF with baoyu-slide-deck merge scripts when images exist.
"""


def topic_dir_for_write(workspace: Path, write_path: Path) -> Path | None:
    """Return slide-deck topic dir if write_path is under slide-deck/<slug>/."""
    try:
        rel = write_path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2 or parts[0] != "slide-deck":
        return None
    return workspace / "slide-deck" / parts[1]


def write_needs_analysis_guard(workspace: Path, write_path: Path) -> bool:
    topic_dir = topic_dir_for_write(workspace, write_path)
    if topic_dir is None:
        return False
    name = write_path.name
    rel_parts = write_path.resolve().relative_to(workspace.resolve()).parts
    if name == "outline.md":
        return True
    if "prompts" in rel_parts:
        return True
    return False
