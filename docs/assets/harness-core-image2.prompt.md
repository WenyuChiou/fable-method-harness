# Image 2.0 source-art manifest

This file records the production intent for `harness-core-image2.png`. The
committed PNG is the canonical source-art layer used by
`scripts/render_readme_visuals.py`; the renderer adds all English, Traditional
Chinese, and benchmark text deterministically.

## Generation

- Tool: OpenAI Image 2.0 through the built-in image generation tool
- Generated: 2026-07-15
- Native output: 1672 × 941 PNG
- Text policy: no words, letters, numbers, logos, or watermark in model output
- Seed and hidden sampler settings: not exposed by the tool

## Production prompt

> Create a clean, premium, text-free editorial illustration sheet for an
> open-source AI-agent harness README. Match the friendly, colorful visual
> language of a polished Awesome-list banner: crisp 2.5D vector-like
> illustration, rounded forms, a recurring sapphire-blue AI orb, white
> background, and vivid blue, teal, purple, and orange accents. Use one 16:9
> landscape canvas with four clearly separated but visually connected scenes,
> all at a consistent scale. Scene 1: the AI orb connects to terminal, code,
> compass, and gear icons to represent multiple CLI entry points. Scene 2: the
> orb sits in a harness while a robot arm selects one purple cartridge from a
> rack, representing selective skill or route loading. Scene 3: the harnessed
> orb branches toward a compass, laptop, and drafting tools, representing
> routing by task character. Scene 4: an evidence lab with a test tube,
> checklist, magnifier, green pass gate, orange halt barrier, and memory
> notebook, representing verification and continuous learning. No text,
> labels, UI copy, brands, or watermark. Leave generous white space for later
> deterministic typography.

## Reproducibility boundary

The prompt and post-processing are versioned, but source-art regeneration is
not bit-exact because Image 2.0 did not expose a seed or sampler configuration.
The committed source PNG plus the deterministic Pillow renderer are therefore
the reproducible inputs for the final bilingual README images.
