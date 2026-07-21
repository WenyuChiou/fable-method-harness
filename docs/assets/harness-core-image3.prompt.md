# Image 2.0 source-art manifest — v3

This file records the production intent for `harness-core-image3.png`. The
committed PNG is the canonical source-art layer for
`scripts/render_readme_visuals.py`; the renderer adds all English, Traditional
Chinese, and benchmark text deterministically.

## Generation

- Tool: OpenAI Image 2.0 through the built-in image generation tool
- Generated: 2026-07-20
- Text policy: no words, letters, numbers, logos, or watermark in model output
- Seed and hidden sampler settings: not exposed by the tool

## Production prompt

> Create a premium, text-free 16:9 editorial illustration for an open-source
> AI-agent harness README. Show one clear connected horizontal story: multi-CLI
> inputs enter a sapphire-blue agent orb; a precision arm selects exactly one
> violet skill card from a rack; the harnessed orb routes work across coding,
> lightweight-router, and planning lanes with a declining token gauge; an
> evidence lab tests the result through green verify and amber halt paths, then
> feeds outcomes back into the route. Use polished 2.5D isometric product
> illustration, navy line work, white space, blue/teal/violet/amber accents,
> and no text, brands, pseudo-words, or watermark.

## Reproducibility boundary

The prompt and post-processing are versioned, but source-art regeneration is
not bit-exact because Image 2.0 does not expose a seed or sampler
configuration. The committed source PNG plus the deterministic Pillow renderer
are therefore the reproducible inputs for the final bilingual README images.
