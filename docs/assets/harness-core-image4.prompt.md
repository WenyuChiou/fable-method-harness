# Image 2.0 source-art manifest — v4

This file records the production intent for `harness-core-image4.png`. The
committed PNG is the canonical source-art layer for
`scripts/render_readme_visuals.py`; the renderer adds all English, Traditional
Chinese, and benchmark text deterministically.

## Generation

- Tool: OpenAI Image 2.0 through the built-in image generation tool
- Generated: 2026-07-20
- Visual direction: dark terminal/dashboard editorial design, aligned with the
  repository owner's other developer-skill README visuals
- Text policy: no words, letters, numbers, logos, or watermark in model output
- Seed and hidden sampler settings: not exposed by the tool

## Production prompt

> Create a text-free dark-mode AI harness control console for a developer-skill
> README: multi-runtime intake feeds a blue agent core; a selector loads one
> violet skill module; coding, router, and planning lanes branch by task; an
> evidence station verifies through green and amber rollback paths and feeds
> the outcome back. Use a polished terminal/dashboard aesthetic, fine linework,
> slate panels, cobalt/cyan/violet/teal/amber signals, and no text or logos.

## Reproducibility boundary

The prompt and post-processing are versioned, but source-art regeneration is
not bit-exact because Image 2.0 does not expose a seed or sampler
configuration. The committed source PNG plus the deterministic Pillow renderer
are therefore the reproducible inputs for the final bilingual README images.
