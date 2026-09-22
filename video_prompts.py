# -*- coding: utf-8 -*-
"""Grok Video / AI video beat builder for Sneaker Image Studio.

Deterministic Generate + Extend prompts (English paste-ready).
Greek one-line summaries for UI when lang=el.
"""
from __future__ import annotations

from typing import Any, Optional


# Carousel story-arc roles (aligned with app.build_carousel_prompts)
CAROUSEL_ROLE_ARCS: dict[int, list[str]] = {
    2: ["hook", "product_cta"],
    3: ["hook", "product", "specs_cta"],
    4: ["hook", "product", "specs", "cta"],
    5: ["hook", "lifestyle", "product", "specs", "cta"],
}

ROLE_LABELS_EN = {
    "start": "Start / Generate",
    "deepen": "Deepen / Extend",
    "end": "Ending / Extend",
    "hook": "Hook / environment",
    "product": "Product hero",
    "product_cta": "Product + soft CTA",
    "lifestyle": "On-foot / lifestyle",
    "specs": "Macro sole / detail",
    "specs_cta": "Macro + ending",
    "cta": "Calm hold / CTA",
    "content": "Story beat",
}

ROLE_SUMMARIES_EL = {
    "start": "Έναρξη: ήρωας προϊόντος ή ήδη στα πόδια + ασφαλής κίνηση κάμερας",
    "deepen": "Συνέχεια: πιο κοντινή γωνία / λεπτομέρεια, ίδιο παπούτσι",
    "end": "Κλείσιμο: ήρεμο κράτημα + υδατογράφημα αν έχει οριστεί",
    "hook": "Άγκιστρο: ευρύ περιβάλλον με ήπια κίνηση κάμερας",
    "product": "Προϊόν: 3/4 ήρωας με αργό push-in ή orbit",
    "product_cta": "Προϊόν + ήπια κλήση: ήρεμο κράτημα",
    "lifestyle": "On-foot: γόνατα κάτω, ακριβώς δύο πόδια, μόνο μπροστά",
    "specs": "Macro: αργή κίνηση στη σόλα / midsole",
    "specs_cta": "Macro + κλείσιμο με υδατογράφημα αν έχει οριστεί",
    "cta": "Ήρεμο flat-lay / hold + υδατογράφημα αν έχει οριστεί",
    "content": "Εκπαιδευτικό beat με ήπια κίνηση κάμερας",
}

HOWTO_EN = (
    "Paste Beat 1 into Grok Video → Generate. "
    "Then Extend with Beat 2, then Extend with Beat 3+ (same session). "
    "Do not jump from empty static shoes into a full runner — use camera motion or already-on-feet from Beat 1."
)

HOWTO_EL = (
    "Βάλε το Beat 1 στο Grok Video → Generate. "
    "Μετά Extend με Beat 2, μετά Extend με Beat 3+ (ίδια συνεδρία). "
    "Μην ξεκινήσεις με άδεια στατικά παπούτσια και μετά runner — κάμερα ή ήδη στα πόδια από το Beat 1."
)


def _clean(s: Any) -> str:
    return (str(s) if s is not None else "").strip()


def _shoe_lock(brand: str, model: str, colorway: str) -> str:
    b, m, c = _clean(brand), _clean(model), _clean(colorway)
    if not (b or m):
        return (
            "Generic authentic running/lifestyle footwear only — soft trademark-safe; "
            "do not invent Nike/Adidas logos or swap brands."
        )
    pair = " ".join(x for x in (b, m, c) if x)
    return (
        f"Lock exact pair: {pair}. Soft trademark-safe {b or 'brand'} silhouette and colors only — "
        f"do not substitute Nike/Adidas/generic; do not invent logos."
    )


def _appearance_video_clause(appearance: str) -> str:
    key = (_clean(appearance) or "eu").lower()
    # Video default: prefer no faces for morph safety unless explicitly showing people
    if key == "no_face" or key in ("auto", "eu", "diverse", ""):
        base = (
            "No faces — waist/knees-down only if a person is shown; crop below chin; "
            "prioritize shoes, legs, hands, props."
        )
        if key == "eu":
            return (
                base
                + " If legs visible: light-to-olive Mediterranean/European adult, natural look."
            )
        if key == "diverse":
            return (
                base
                + " If legs visible: naturally diverse adult appropriate to EU street footwear content."
            )
        return base
    return "No faces unless required; prefer waist/knees-down footwear focus."


def _no_chrome() -> str:
    return (
        "No UI chrome: no Slide X of Y, no LEARN MORE buttons, no carousel dots, "
        "no invented badges (OFFICIAL SELECTION / BESTSELLER) unless explicitly in watermark field."
    )


def _watermark_clause(watermark: str, *, final_beat: bool) -> str:
    w = _clean(watermark)
    if not w:
        return "No watermark, no domain text on screen."
    if final_beat:
        return (
            f"One readable watermark bottom-right only: {w} "
            f"(phone-readable, clean sans-serif, strong contrast, ~2–3% edge margin; not dominating the shoe)."
        )
    return "No watermark yet — keep frame clean for Extend continuity."


def _continuity() -> str:
    return (
        "Continue seamlessly from the previous clip — same exact pair, same lighting continuity, "
        "same environment family; no morphing into a different shoe or brand."
    )


def _safe_motion_rules() -> str:
    return (
        "SAFE MOTION ONLY: prefer slow push-in, gentle orbit, or slight tilt (camera-only). "
        "If on-foot: already on feet from this beat — light walk from knees-down with exactly two legs/feet, "
        "FORWARD only, no reverse, no spins/pirouettes, no complex full running gait "
        "(avoids moonwalk/morph). Never start as static empty shoes then jump to a runner on Extend."
    )


def _env_hint(env: str, problem: str, goal: str) -> str:
    bits = []
    if _clean(env):
        bits.append(_clean(env))
    if _clean(problem):
        bits.append(f"mood hint: {_clean(problem)}")
    if _clean(goal) and _clean(goal).lower() not in ("auto", "content", ""):
        bits.append(f"goal angle: {_clean(goal)}")
    if not bits:
        return "clean athletic commercial setting"
    return "; ".join(bits)


def _specs_hint(specs: str) -> str:
    s = _clean(specs)
    return f" Materials/detail cues: {s}." if s else ""


def _beat_prompt(
    *,
    index: int,
    role: str,
    brand: str,
    model: str,
    colorway: str,
    specs: str,
    env: str,
    problem: str,
    goal: str,
    watermark: str,
    appearance: str,
    is_final: bool,
    motion_focus: str,
    topic: str = "",
    slide_title: str = "",
    slide_body: str = "",
    product_mode: bool = True,
) -> str:
    parts: list[str] = []
    if index == 1:
        parts.append(
            "Photorealistic commercial video, 9:16 vertical. Generate this opening beat."
        )
    else:
        parts.append("Extend this clip.")
        parts.append(_continuity())

    parts.append(_safe_motion_rules())
    parts.append(_appearance_video_clause(appearance))
    parts.append(_no_chrome())

    if product_mode and (_clean(brand) or _clean(model)):
        parts.append(_shoe_lock(brand, model, colorway))
        parts.append(_specs_hint(specs))
        scene = _env_hint(env, problem, goal)
        parts.append(f"Setting: {scene}.")
    else:
        topic_bit = _clean(topic) or "educational sneaker care / footwear tips"
        parts.append(
            f"Educational footwear story about: {topic_bit}. "
            "Generic authentic sneakers OK — soft trademark-safe; no Nike/Adidas logo inventing."
        )
        if _clean(slide_title) or _clean(slide_body):
            parts.append(
                f"Story beat focus: {_clean(slide_title)}. {_clean(slide_body)}".strip()
            )

    parts.append(motion_focus)
    parts.append(_watermark_clause(watermark, final_beat=is_final))
    parts.append("Natural light continuity. Cinematic, sharp, no morphing shoes.")
    return " ".join(p.strip() for p in parts if p and p.strip())


def _motion_for_role(role: str, *, brand: str, model: str, colorway: str, product_mode: bool) -> str:
    pair = " ".join(x for x in (_clean(brand), _clean(model), _clean(colorway)) if x)
    shoe = pair if (product_mode and pair) else "the sneakers"

    motions = {
        "start": (
            f"START with product hero of {shoe} already in frame — slow push-in camera-only motion "
            f"(or already on feet knees-down). Do NOT begin with empty static shoes that later become a runner."
        ),
        "deepen": (
            f"Deepen: gentle orbit or slow tilt toward sole/midsole macro of {shoe}; "
            f"same pair locked; no new brand."
        ),
        "end": (
            f"Calm hold on {shoe} after a brief soft settle — fade-friendly ending still for Shorts."
        ),
        "hook": (
            f"Wide establishing lifestyle beat; {shoe} visible small or already on feet knees-down; "
            f"slow push-in or gentle handheld micro-move — not empty-shoes-to-runner jump."
        ),
        "product": (
            f"Clean 3/4 product hero of {shoe}; smooth slow push-in; shoes slightly staggered; "
            f"camera-only motion."
        ),
        "product_cta": (
            f"Clean 3/4 product hero of {shoe} settling into a calm hold for soft CTA space; "
            f"camera slows to still."
        ),
        "lifestyle": (
            f"On-foot crop from knees/waist down — exactly two legs/feet wearing {shoe}; "
            f"light forward walk only (no reverse, no spins, no full sprint gait)."
        ),
        "specs": (
            f"MACRO fill-frame slow glide across midsole/outsole of {shoe}; "
            f"gentle orbit; no full-pair bench still morph."
        ),
        "specs_cta": (
            f"MACRO midsole detail of {shoe} then ease back to a calm readable hold."
        ),
        "cta": (
            f"Top-down flat lay OR calm side hold of {shoe} with soft landing energy for end card."
        ),
        "content": (
            f"Slow push-in or gentle orbit supporting the educational story; "
            f"footwear readable; no chaotic motion."
        ),
    }
    return motions.get(role, motions["content"])


def _summary_for_role(role: str, lang: str, index: int) -> str:
    if (lang or "el").lower() == "el":
        base = ROLE_SUMMARIES_EL.get(role, ROLE_SUMMARIES_EL["content"])
        return f"Beat {index}: {base}"
    label = ROLE_LABELS_EN.get(role, role)
    return f"Beat {index}: {label} — paste into Grok Video ({'Generate' if index == 1 else 'Extend'})"


def _duration_hint(n: int) -> str:
    if n == 3:
        return "~16s (3× ~5s)"
    if n < 3:
        return f"~{n * 5}s ({n}× ~5s) — Short"
    return f"~{n * 5}s ({n}× ~5s) — longer carousel video; trim if needed"


def format_video_prompts_txt(
    video_pack: dict[str, Any],
    *,
    brand: str = "",
    model: str = "",
    colorway: str = "",
    topic: str = "",
) -> str:
    """Plain-text export for download / ZIP."""
    beats = video_pack.get("beats") or []
    lines = [
        "Sneakerness — Grok Video / AI video beats",
        "How to use: Beat 1 → Generate → Extend with Beat 2 → Extend with Beat 3+",
        "",
    ]
    product = " ".join(x for x in (_clean(brand), _clean(model), _clean(colorway)) if x)
    if product:
        lines.append(f"Product: {product}")
    if _clean(topic):
        lines.append(f"Topic: {_clean(topic)}")
    lines.append(f"Duration hint: {video_pack.get('duration_hint') or ''}")
    lines.append(f"Howto: {video_pack.get('howto_en') or HOWTO_EN}")
    lines.append("")
    for b in beats:
        idx = b.get("index", "")
        role = b.get("role", "")
        label = ROLE_LABELS_EN.get(role, role)
        action = "Generate" if idx == 1 else "Extend"
        lines.append(f"========== BEAT {idx} — {label} ({action}) ==========")
        lines.append("")
        lines.append(_clean(b.get("prompt_en")))
        lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_grok_video_beats(
    brand: str = "",
    model: str = "",
    colorway: str = "",
    specs: str = "",
    env: str = "",
    props: str = "",  # reserved for future prop hints
    problem: str = "",
    watermark: str = "",
    appearance: str = "eu",
    goal: str = "auto",
    mode: str = "single",
    slide_count: int = 3,
    slide_prompts: Optional[list] = None,  # unused; roles drive motion
    slide_texts: Optional[list] = None,
    lang: str = "el",
    topic: str = "",
) -> dict[str, Any]:
    """Build deterministic Grok Video beats.

    mode:
      - single: always 3 beats (~16s)
      - carousel: N = slide_count (2–5), one beat per slide role
      - content: N from slide_texts / slide_count; topic-driven, soft product lock
    """
    _ = props  # kept in signature for scene parity with callers
    _ = slide_prompts
    mode_l = (_clean(mode) or "single").lower()
    product_mode = mode_l != "content"
    wm = _clean(watermark)

    if mode_l == "carousel":
        try:
            n = int(slide_count)
        except (TypeError, ValueError):
            n = 3
        if n not in (2, 3, 4, 5):
            n = 3
        roles = list(CAROUSEL_ROLE_ARCS[n])
    elif mode_l == "content":
        texts = list(slide_texts or [])
        n = len(texts) if texts else max(2, min(5, int(slide_count or 3)))
        if n < 2:
            n = 2
        if n > 5:
            n = 5
        # Map educational slides onto a simplified arc
        content_arcs = {
            2: ["hook", "cta"],
            3: ["hook", "product", "cta"],
            4: ["hook", "product", "specs", "cta"],
            5: ["hook", "lifestyle", "product", "specs", "cta"],
        }
        roles = list(content_arcs.get(n, content_arcs[3]))
        while len(texts) < n:
            texts.append({})
    else:
        # single layout — always 3 beats
        n = 3
        roles = ["start", "deepen", "end"]
        texts = []

    beats: list[dict[str, Any]] = []
    for i, role in enumerate(roles, start=1):
        is_final = i == n
        slide_title = ""
        slide_body = ""
        if mode_l == "content" and texts:
            item = texts[i - 1] if i - 1 < len(texts) else {}
            if isinstance(item, dict):
                slide_title = _clean(item.get("title"))
                slide_body = _clean(item.get("body"))
            else:
                slide_body = _clean(item)

        motion = _motion_for_role(
            role, brand=brand, model=model, colorway=colorway, product_mode=product_mode
        )
        prompt_en = _beat_prompt(
            index=i,
            role=role,
            brand=brand,
            model=model,
            colorway=colorway,
            specs=specs,
            env=env,
            problem=problem,
            goal=goal,
            watermark=wm,
            appearance=appearance,
            is_final=is_final,
            motion_focus=motion,
            topic=topic,
            slide_title=slide_title,
            slide_body=slide_body,
            product_mode=product_mode,
        )
        beats.append(
            {
                "index": i,
                "role": role,
                "prompt_en": prompt_en,
                "summary_el": _summary_for_role(role, lang, i),
            }
        )

    return {
        "beats": beats,
        "howto_el": HOWTO_EL,
        "howto_en": HOWTO_EN,
        "duration_hint": _duration_hint(n),
        "mode": mode_l,
    }


def ensure_video_beats(
    existing: Any,
    **kwargs,
) -> dict[str, Any]:
    """Return existing video_beats dict if valid; else rebuild from kwargs."""
    if isinstance(existing, dict) and existing.get("beats"):
        return existing
    return build_grok_video_beats(**kwargs)
