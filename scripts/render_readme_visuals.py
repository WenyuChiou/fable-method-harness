#!/usr/bin/env python3
"""Render the illustrated bilingual README overview.

Image 2.0 supplies the text-free character art. Pillow owns every label and
benchmark number so the English and Traditional Chinese editions remain
deterministic, reviewable, and evidence-bound.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
ART = ASSETS / "harness-core-image4.png"
WIDTH, HEIGHT = 2048, 1480

COLORS = {
    "paper": "#0B101A",
    "navy": "#F4F7FF",
    "ink": "#E4EAF7",
    "muted": "#AAB6CD",
    "line": "#2B3850",
    "pale": "#17243A",
    "blue": "#61A7FF",
    "purple": "#A581FF",
    "teal": "#35D4B1",
    "amber": "#FFB454",
    "amber_pale": "#3B2B18",
}

def first_existing_font(label: str, *candidates: str) -> Path:
    """Resolve an authoring font on Windows, Linux, or macOS."""
    for candidate in map(Path, candidates):
        if candidate.exists():
            return candidate
    searched = "\n  - ".join(candidates)
    raise FileNotFoundError(f"No {label} font found. Searched:\n  - {searched}")


FONT_EN = first_existing_font(
    "English regular",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
FONT_EN_BOLD = first_existing_font(
    "English bold",
    r"C:\Windows\Fonts\segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
FONT_TC = first_existing_font(
    "Traditional Chinese regular",
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\NotoSansTC-VF.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansTC-Regular.otf",
    "/System/Library/Fonts/PingFang.ttc",
)
FONT_TC_BOLD = first_existing_font(
    "Traditional Chinese bold",
    r"C:\Windows\Fonts\msjhbd.ttc",
    r"C:\Windows\Fonts\NotoSansTC-VF.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansTC-Bold.otf",
    "/System/Library/Fonts/PingFang.ttc",
)


COPY = {
    "en": {
        "eyebrow": "FABLE-METHOD HARNESS  /  EVIDENCE-DRIVEN",
        "title": "AI harness — load less. finish with evidence.",
        "subtitle": "One adaptive workflow across Claude Code, Codex / Cursor, Hermes, and Shell / CI.",
        "stages": [
            {
                "title": "MULTI-CLI ENTRY",
                "lead": "Meet each runtime where it starts",
                "lines": ["SKILL.md · AGENTS.md", "HERMES.md · Python runners"],
            },
            {
                "title": "LOAD ONE SKILL / ROUTE",
                "lead": "Classify first; keep the rest dormant",
                "lines": ["No repository-wide context dump", "route_pack.py = one-call context"],
            },
            {
                "title": "ROUTE BY TASK",
                "lead": "Use the lightest surface that can pass",
                "lines": ["Hermes routine · Codex mechanical", "Claude judgment / orchestration"],
            },
            {
                "title": "VERIFY, THEN LEARN",
                "lead": "Test → SHIP / HALT → evidence memory",
                "lines": ["Pre-register A/B experiments", "Keep winners; remove losers"],
            },
        ],
        "loop": "verified outcomes improve the next route",
        "metrics_title": "MEASURED EFFICIENCY  /  RESULTS FROM THE REPOSITORY EVIDENCE",
        "metrics": [
            {
                "tag": "CODEX  /  LONG TASKS",
                "value": "-27%",
                "label": "input tokens",
                "pills": ["-59% tool calls", "-34% wall-clock"],
                "note": "inline micro-contract · 80 executed trials",
            },
            {
                "tag": "HERMES  /  ROUTINE WORK",
                "value": "-69.9%",
                "label": "fixed project context",
                "pills": ["5,994 B → 1,803 B"],
                "note": "offline bytes · not API tokens / cost / latency",
            },
            {
                "tag": "ONE-CALL ORIENTATION",
                "value": "0.72×",
                "label": "total cost",
                "pills": ["11.3 vs 16.0 turns"],
                "note": "route_pack.py · live A/B",
            },
            {
                "tag": "COST ROUTING",
                "value": "0.37×",
                "label": "all-strong cost proxy",
                "pills": ["quality 3/3 = 3/3"],
                "note": "blind routing 30/30 · 0 honesty mis-routes",
            },
        ],
        "boundary": "EVIDENCE BOUNDARY  /  Workflow efficiency only — no claim of higher model capability.",
    },
    "zh-TW": {
        "eyebrow": "FABLE-METHOD HARNESS  /  實證驅動",
        "title": "AI Harness：少載入，以證據完成。",
        "subtitle": "Claude Code、Codex / Cursor、Hermes 與 Shell / CI，共用一套自適應工作流程。",
        "stages": [
            {
                "title": "多種 CLI 入口",
                "lead": "從每個 runtime 原生的入口開始",
                "lines": ["SKILL.md · AGENTS.md", "HERMES.md · Python runners"],
            },
            {
                "title": "只載入一個 SKILL / ROUTE",
                "lead": "先分類；其餘脈絡保持休眠",
                "lines": ["不把整個 repository 塞進 context", "route_pack.py = 一次呼叫脈絡"],
            },
            {
                "title": "依任務性質路由",
                "lead": "使用能通過品質門檻的最輕介面",
                "lines": ["Hermes 日常 · Codex 機械式", "Claude 判斷 / 編排"],
            },
            {
                "title": "先驗證，再學習",
                "lead": "測試 → SHIP / HALT → evidence memory",
                "lines": ["預先登記 A/B 實驗", "保留贏家；移除輸家"],
            },
        ],
        "loop": "通過驗證的結果，改善下一次路由",
        "metrics_title": "實測效率  /  來自專案證據的結果",
        "metrics": [
            {
                "tag": "CODEX  /  長任務",
                "value": "-27%",
                "label": "輸入 tokens",
                "pills": ["-59% 工具呼叫", "-34% 執行時間"],
                "note": "inline micro-contract · 80 次已執行試驗",
            },
            {
                "tag": "HERMES  /  日常工作",
                "value": "-69.9%",
                "label": "固定專案脈絡",
                "pills": ["5,994 B → 1,803 B"],
                "note": "離線 bytes · 不是 API tokens / 成本 / 延遲",
            },
            {
                "tag": "一次呼叫導覽",
                "value": "0.72×",
                "label": "總成本",
                "pills": ["11.3 vs 16.0 回合"],
                "note": "route_pack.py · live A/B",
            },
            {
                "tag": "成本路由",
                "value": "0.37×",
                "label": "全強模型成本代理值",
                "pills": ["品質 3/3 = 3/3"],
                "note": "盲測路由 30/30 · 誠實性誤路由 0",
            },
        ],
        "boundary": "證據邊界  /  數字只代表工作流程效率，不宣稱模型能力提升。",
    },
}


def font(
    size: int,
    *,
    bold: bool = False,
    lang: str = "en",
) -> ImageFont.FreeTypeFont:
    """Load the project authoring fonts with explicit CJK weight selection."""
    if lang == "en":
        return ImageFont.truetype(str(FONT_EN_BOLD if bold else FONT_EN), size)
    selected = FONT_TC_BOLD if bold else FONT_TC
    result = ImageFont.truetype(str(selected), size)
    if selected.name == "NotoSansTC-VF.ttf":
        result.set_variation_by_name("Bold" if bold else "Regular")
    return result


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def rounded_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    outline: str = COLORS["line"],
    radius: int = 26,
    shadow: bool = True,
) -> None:
    """Draw a light editorial card with a quiet navy shadow."""
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(canvas, "RGBA")
    if shadow:
        draw.rounded_rectangle(
            (x1 + 4, y1 + 9, x2 + 4, y2 + 9),
            radius=radius,
            fill=(0, 0, 0, 120),
        )
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=(19, 27, 42, 246),
        outline=rgb(outline) + (255,),
        width=2,
    )


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    lang: str,
    fill: str = COLORS["pale"],
    color: str = COLORS["navy"],
    size: int = 22,
) -> int:
    label_font = font(size, bold=True, lang=lang)
    bounds = draw.textbbox((0, 0), text, font=label_font)
    width = bounds[2] - bounds[0] + 34
    x, y = xy
    draw.rounded_rectangle((x, y, x + width, y + 42), radius=18, fill=fill)
    draw.text((x + 17, y + 6), text, font=label_font, fill=color)
    return width


def add_illustration(canvas: Image.Image) -> None:
    """Place the Image 2.0 scene strip as the visual architecture backbone."""
    art = Image.open(ART).convert("RGB")
    # The source has generous white margins. This crop preserves all four
    # illustrated scenes while giving them enough scale for a README hero.
    art = art.crop((0, 115, art.width, 835))
    art = ImageOps.fit(
        art,
        (1904, 670),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    canvas.paste(art, (72, 230))


def draw_flow_connectors(canvas: Image.Image) -> None:
    """Connect the four illustrated scenes without covering their focal art."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    centers = (301, 783, 1265, 1747)
    colors = (COLORS["blue"], COLORS["purple"], COLORS["teal"])
    for left, right, color in zip(centers, centers[1:], colors):
        draw.line((left + 112, 668, right - 112, 668), fill=rgb(color) + (190,), width=8)
        draw.polygon(
            ((right - 112, 668), (right - 136, 654), (right - 136, 682)),
            fill=rgb(color) + (220,),
        )


def stage_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    stage: dict[str, object],
    *,
    number: int,
    accent: str,
    lang: str,
) -> None:
    rounded_card(canvas, box)
    draw = ImageDraw.Draw(canvas)
    x1, y1, x2, _ = box
    draw.rounded_rectangle((x1, y1, x2, y1 + 8), radius=4, fill=accent)
    draw.ellipse((x1 + 24, y1 + 24, x1 + 70, y1 + 70), fill=accent)
    number_font = font(20, bold=True, lang="en")
    number_text = f"{number:02d}"
    number_box = draw.textbbox((0, 0), number_text, font=number_font)
    draw.text(
        (x1 + 47 - (number_box[2] - number_box[0]) / 2, y1 + 33),
        number_text,
        font=number_font,
        fill="white",
    )
    title_size = 21 if lang == "en" else 23
    draw.text(
        (x1 + 84, y1 + 29),
        str(stage["title"]),
        font=font(title_size, bold=True, lang=lang),
        fill=COLORS["navy"],
    )
    draw.text(
        (x1 + 26, y1 + 88),
        str(stage["lead"]),
        font=font(20 if lang == "en" else 21, bold=True, lang=lang),
        fill=COLORS["ink"],
    )
    for index, line in enumerate(stage["lines"]):
        y = y1 + 129 + index * 34
        draw.ellipse((x1 + 28, y + 9, x1 + 37, y + 18), fill=accent)
        draw.text(
            (x1 + 49, y),
            str(line),
            font=font(18 if lang == "en" else 19, lang=lang),
            fill=COLORS["muted"],
        )


def metric_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    metric: dict[str, object],
    *,
    lang: str,
    accent: str,
) -> None:
    rounded_card(canvas, box, radius=24)
    draw = ImageDraw.Draw(canvas)
    x1, y1, _, y2 = box
    draw.rounded_rectangle((x1, y1, x1 + 10, y2), radius=5, fill=accent)
    draw.text(
        (x1 + 30, y1 + 23),
        str(metric["tag"]),
        font=font(19, bold=True, lang=lang),
        fill=accent,
    )
    draw.text(
        (x1 + 28, y1 + 57),
        str(metric["value"]),
        font=font(62, bold=True, lang=lang),
        fill=COLORS["navy"],
    )
    draw.text(
        (x1 + 30, y1 + 132),
        str(metric["label"]),
        font=font(25, bold=True, lang=lang),
        fill=COLORS["ink"],
    )
    x = x1 + 30
    for label in metric["pills"]:
        x += pill(
            draw,
            (x, y1 + 175),
            str(label),
            lang=lang,
            fill=COLORS["amber_pale"] if accent == COLORS["amber"] else COLORS["pale"],
            size=19,
        ) + 8
    note = str(metric["note"])
    warning = "not API" in note or "不是 API" in note
    draw.text(
        (x1 + 30, y2 - 37),
        note,
        font=font(16 if lang == "en" else 17, lang=lang),
        fill="#FFCB78" if warning else COLORS["muted"],
    )


def render(lang: str) -> Path:
    copy = COPY[lang]
    canvas = Image.new("RGB", (WIDTH, HEIGHT), COLORS["paper"])
    draw = ImageDraw.Draw(canvas)

    # Editorial header: large enough to remain legible in GitHub's README width.
    pill(
        draw,
        (72, 38),
        str(copy["eyebrow"]),
        lang=lang,
        fill=COLORS["pale"],
        color=COLORS["blue"],
        size=20,
    )
    draw.text(
        (72, 96),
        str(copy["title"]),
        font=font(61 if lang == "en" else 58, bold=True, lang=lang),
        fill=COLORS["navy"],
    )
    draw.text(
        (76, 174),
        str(copy["subtitle"]),
        font=font(27 if lang == "en" else 28, lang=lang),
        fill=COLORS["muted"],
    )

    add_illustration(canvas)
    draw_flow_connectors(canvas)

    stage_boxes = (
        (72, 700, 530, 916),
        (554, 700, 1012, 916),
        (1036, 700, 1494, 916),
        (1518, 700, 1976, 916),
    )
    accents = (COLORS["blue"], COLORS["purple"], COLORS["teal"], COLORS["amber"])
    for index, (box, stage, accent) in enumerate(
        zip(stage_boxes, copy["stages"], accents),
        start=1,
    ):
        stage_card(canvas, box, stage, number=index, accent=accent, lang=lang)

    draw = ImageDraw.Draw(canvas)
    draw.arc((612, 892, 1708, 990), start=0, end=180, fill=COLORS["teal"], width=5)
    draw.polygon(((612, 940), (636, 927), (636, 953)), fill=COLORS["teal"])
    loop_text = str(copy["loop"])
    loop_font = font(18, bold=True, lang=lang)
    loop_box = draw.textbbox((0, 0), loop_text, font=loop_font)
    draw.text(
        ((WIDTH - (loop_box[2] - loop_box[0])) / 2, 934),
        loop_text,
        font=loop_font,
        fill=COLORS["teal"],
    )

    draw.text(
        (72, 983),
        str(copy["metrics_title"]),
        font=font(22, bold=True, lang=lang),
        fill=COLORS["navy"],
    )
    metric_boxes = (
        (72, 1025, 530, 1378),
        (554, 1025, 1012, 1378),
        (1036, 1025, 1494, 1378),
        (1518, 1025, 1976, 1378),
    )
    for box, metric, accent in zip(metric_boxes, copy["metrics"], accents):
        metric_card(canvas, box, metric, lang=lang, accent=accent)

    draw = ImageDraw.Draw(canvas)
    draw.line((72, 1415, 1976, 1415), fill=COLORS["line"], width=2)
    draw.text(
        (72, 1431),
        str(copy["boundary"]),
        font=font(18, bold=True, lang=lang),
        fill=COLORS["muted"],
    )

    output = ASSETS / (
        "readme-harness.en.png" if lang == "en" else "readme-harness.zh-TW.png"
    )
    canvas.save(output, format="PNG", optimize=True, compress_level=9)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("en", "zh-TW", "all"), default="all")
    args = parser.parse_args()
    if not ART.exists():
        parser.error(f"missing Image 2.0 art layer: {ART}")
    languages = ("en", "zh-TW") if args.lang == "all" else (args.lang,)
    for language in languages:
        print(render(language))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
