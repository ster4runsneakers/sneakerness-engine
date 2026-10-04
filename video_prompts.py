# -*- coding: utf-8 -*-
"""Grok Video / AI video beat builder for Sneaker Image Studio.

Deterministic Generate + Extend prompts (English paste-ready).
Greek one-line summaries for UI when lang=el.
"""
from __future__ import annotations

import re
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


VIDEO_FINAL_CHECK = (
    "Final check: correct sneaker model/colorway, accurate logo, legible correct text, "
    "no extra fingers/limbs, no bare feet, no third-party brands."
)


# ---------------------------------------------------------------------------
# AUDIO: scene-matched instrumental music, never narration
# ---------------------------------------------------------------------------
AUDIO_NO_VOICE = (
    "Audio: instrumental background music only. NO voiceover, NO narration, NO spoken words, "
    "NO dialogue, NO singing/lyrics, NO text-to-speech."
)

VIDEO_AUDIO_NEGATIVES = (
    "Negatives (audio): voiceover, narration, narrator, spoken words, dialogue, talking, "
    "lyrics, singing, vocals, text-to-speech."
)

# key -> (EN style clause, EL summary label, EN summary label, ambient cue)
MUSIC_PROFILES: dict[str, tuple[str, str, str, str]] = {
    "beach": (
        "light upbeat acoustic / tropical house instrumental, relaxed sunny mood, ~100-110 BPM",
        "ελαφρύ acoustic / tropical house, χαλαρό",
        "light acoustic / tropical house, relaxed",
        "soft waves and light footsteps",
    ),
    "mountain": (
        "uplifting cinematic indie-folk instrumental, airy and open, ~90-105 BPM",
        "ανεβαστικό cinematic indie/folk, ευάερο",
        "uplifting cinematic indie/folk, airy",
        "light wind and footsteps on the trail",
    ),
    "running": (
        "energetic electronic instrumental with a driving beat, motivated mood, ~120-128 BPM",
        "ενεργητικό electronic, δυναμικός ρυθμός ~120-128 BPM",
        "energetic electronic, driving beat ~120-128 BPM",
        "rhythmic footsteps",
    ),
    "gym": (
        "punchy hip-hop / electronic instrumental beat, powerful focused mood, ~95-110 BPM",
        "δυνατό hip-hop / electronic beat",
        "punchy hip-hop / electronic beat",
        "subtle gym ambience",
    ),
    "basketball": (
        "bouncy hip-hop instrumental beat, playful confident mood, ~90-100 BPM",
        "χοροπηδηχτό hip-hop beat",
        "bouncy hip-hop beat",
        "subtle sneaker squeaks and ball bounces",
    ),
    "commute": (
        "moody downtempo / lo-fi instrumental, calm reflective mood, ~75-85 BPM",
        "μελαγχολικό downtempo / lo-fi, ήρεμο",
        "moody downtempo / lo-fi, calm",
        "soft rain or distant station ambience",
    ),
    "cafe": (
        "warm jazzy lo-fi instrumental, cozy easygoing mood, ~80-90 BPM",
        "ζεστό jazzy lo-fi, χαλαρό",
        "warm jazzy lo-fi, cozy",
        "soft cafe ambience",
    ),
    "travel": (
        "smooth chill electronic instrumental, light forward-moving mood, ~100-110 BPM",
        "απαλό chill electronic, ταξιδιάρικο",
        "smooth chill electronic, travel mood",
        "subtle terminal ambience and rolling suitcase",
    ),
    "recovery": (
        "soft ambient / lo-fi instrumental, calm restful mood, ~65-75 BPM",
        "απαλό ambient / lo-fi, ήρεμο",
        "soft ambient / lo-fi, restful",
        "quiet room tone",
    ),
    "city": (
        "modern lo-fi hip-hop / chill urban groove instrumental, laid-back mood, ~85-95 BPM",
        "μοντέρνο lo-fi hip-hop / chill urban groove",
        "modern lo-fi hip-hop / chill urban groove",
        "light street ambience and footsteps",
    ),
    "default": (
        "modern upbeat chill pop instrumental, positive easygoing mood, ~100-110 BPM",
        "μοντέρνο χαλαρό upbeat pop (instrumental)",
        "modern upbeat chill pop instrumental",
        "light footsteps",
    ),
}

# Order matters: more specific scenes first.
_MUSIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("basketball", ("basketball", "hoop", "court", "μπάσκετ")),
    ("commute", ("rain", "rainy", "metro", "subway", "commut", "train", "platform", "station",
                 "tram", "bus stop", "βροχ", "μετρό", "αποβάθρ", "σταθμ")),
    ("running", ("running", "runner", "run ", "jog", "track", "marathon", "sprint", "τρέξιμ", "στίβ")),
    ("gym", ("gym", "workout", "weights", "dumbbell", "barbell", "fitness", "crossfit", "γυμναστ")),
    ("mountain", ("mountain", "trail", "hike", "hiking", "forest", "summit", "alpine", "βουν", "μονοπάτ")),
    ("beach", ("beach", "coast", "seaside", "shore", "sand", "aegean", "island", "promenade", "sea ",
               "παραλ", "θάλασσ", "αιγαί", "νησ")),
    ("travel", ("airport", "travel", "terminal", "suitcase", "luggage", "flight", "boarding",
                "αεροδρόμ", "ταξίδ")),
    ("cafe", ("cafe", "café", "coffee", "office", "desk", "workday", "shift", "barista", "καφέ", "γραφεί")),
    ("recovery", ("recovery", "loft", "home", "living room", "sofa", "couch", "bedroom", "rest day",
                  "ξεκούρασ", "σπίτ")),
    ("city", ("city", "street", "urban", "plateia", "plaza", "square", "downtown", "sidewalk",
              "crosswalk", "πόλη", "δρόμ", "πλατεί")),
]

_VIBE_TO_MUSIC = {
    "running": "running",
    "trail": "mountain",
    "gym": "gym",
    "street": "city",
    "commute": "commute",
    "work": "cafe",
    "travel": "travel",
    "recovery": "recovery",
    "basketball": "basketball",
}


def _match_music_key(text: str) -> str:
    t = f" {(text or '').lower()} "
    for key, words in _MUSIC_KEYWORDS:
        for w in words:
            if w in t:
                return key
    return ""


def music_key_for_scene(env: str = "", props: str = "", problem: str = "", vibe: str = "",
                        extra: str = "") -> str:
    """Pick a music profile key. Explicit scene vibe wins; else environment keywords,
    then props/problem/extra (topic, slide hints); else default."""
    v = (_clean(vibe) or "auto").lower()
    if v in _VIBE_TO_MUSIC:
        return _VIBE_TO_MUSIC[v]
    k = _match_music_key(env)
    if k:
        return k
    k = _match_music_key(" ".join(x for x in (_clean(props), _clean(problem), _clean(extra)) if x))
    return k or "default"


def music_clause_for_scene(env: str = "", props: str = "", problem: str = "", vibe: str = "",
                           extra: str = "", *, story: bool = False) -> str:
    """English AUDIO block for Grok Video prompts: scene-matched instrumental, no voice."""
    key = music_key_for_scene(env, props, problem, vibe, extra)
    style, _el, _en, ambient = MUSIC_PROFILES.get(key, MUSIC_PROFILES["default"])
    scope = (
        "one consistent track across the whole video that matches the overall story arc, "
        "building gently and resolving on the final hold"
        if story
        else "consistent across Extend clips"
    )
    return (
        f"{AUDIO_NO_VOICE} Music style: {style}; {scope}. "
        f"Subtle natural ambient sound OK under the music ({ambient}) — never voices."
    )


def music_summary_for_scene(env: str = "", props: str = "", problem: str = "", vibe: str = "",
                            extra: str = "", *, lang: str = "el") -> str:
    key = music_key_for_scene(env, props, problem, vibe, extra)
    _style, el, en, _amb = MUSIC_PROFILES.get(key, MUSIC_PROFILES["default"])
    if (lang or "el").lower() == "el":
        return f"Μουσική: {el}, χωρίς αφήγηση"
    return f"Music: {en}, no narration"


def _no_chrome() -> str:
    return (
        "No UI chrome: no Slide X of Y, no LEARN MORE buttons, no carousel dots; "
        "no badges, seals, stamps, star ratings or review marks on screen. "
        "Any on-screen text minimal, plain English, spelled exactly — no garbled or invented words. "
        "People always wear the sneakers or proper shoes — no bare feet. "
        "Props unbranded — no recognizable third-party brands/logos (no AirPods, iPhone, "
        "Apple Watch-like devices)."
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
    audio_clause: str = "",
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
    parts.append(audio_clause or AUDIO_NO_VOICE)
    parts.append(VIDEO_AUDIO_NEGATIVES)
    parts.append(VIDEO_FINAL_CHECK)
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
    if _clean(video_pack.get("music_summary_en")):
        lines.append(f"Audio — {_clean(video_pack.get('music_summary_en'))} (instrumental only, no voiceover)")
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
    vibe: str = "",
) -> dict[str, Any]:
    """Build deterministic Grok Video beats.

    mode:
      - single: always 3 beats (~16s)
      - carousel: N = slide_count (2–5), one beat per slide role
      - content: N from slide_texts / slide_count; topic-driven, soft product lock
    """
    _ = slide_prompts
    mode_l = (_clean(mode) or "single").lower()
    _music_extra = _clean(topic)
    if slide_texts:
        for _it in slide_texts:
            if isinstance(_it, dict):
                _music_extra += " " + _clean(_it.get("title")) + " " + _clean(_it.get("body"))
            else:
                _music_extra += " " + _clean(_it)
    audio_clause = music_clause_for_scene(
        env, props, problem, vibe, _music_extra, story=(mode_l != "single")
    )
    music_el = music_summary_for_scene(env, props, problem, vibe, _music_extra, lang="el")
    music_en = music_summary_for_scene(env, props, problem, vibe, _music_extra, lang="en")
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
            audio_clause=audio_clause,
        )
        _summ = _summary_for_role(role, lang, i)
        if i == 1:
            _summ = f"{_summ} · {music_el if (lang or 'el').lower() == 'el' else music_en}"
        beats.append(
            {
                "index": i,
                "role": role,
                "prompt_en": prompt_en,
                "summary_el": _summ,
            }
        )

    return {
        "beats": beats,
        "howto_el": HOWTO_EL,
        "howto_en": HOWTO_EN,
        "duration_hint": _duration_hint(n),
        "mode": mode_l,
        "music_summary_el": music_el,
        "music_summary_en": music_en,
        "music_summary": music_el if (lang or "el").lower() == "el" else music_en,
    }




UNIFIED_HOWTO_EN = (
    "Paste this ONE English prompt into Grok Video as a single Generate "
    "(~16s, 9:16). Timed beats inside the prompt (0-5s / 5-11s / 11-16s) "
    "are one continuous story — do NOT use Extend for each beat."
)

UNIFIED_HOWTO_EL = (
    "Επικόλλησε αυτό το ΕΝΑ αγγλικό prompt στο Grok Video ως ένα Generate "
    "(~16s, 9:16). Τα timed beats μέσα στο prompt (0-5s / 5-11s / 11-16s) "
    "είναι μία συνεχής ιστορία — ΜΗΝ κάνεις Extend για κάθε beat."
)


def _anatomy_video_clause() -> str:
    return (
        "ANATOMY & COMPOSITION SAFETY: max one person (prefer product + camera motion only); "
        "coherent anatomy — exactly two arms, two legs, two feet, limbs attached; "
        "person supported on ground/bench — never floating; shoes worn on that person OR "
        "product still-life with no people; BAN multi-person foot chaos, extra/detached limbs, "
        "merged bodies, disembodied feet, bare feet."
    )


def _time_windows(n: int) -> list[tuple[str, str]]:
    """Return (label, role-ish focus key) timing windows for n slides, totaling ~16s."""
    if n <= 1:
        return [("0-16s", "product")]
    if n == 2:
        return [("0-8s", "hook"), ("8-16s", "product_cta")]
    if n == 3:
        return [("0-5s", "hook"), ("5-11s", "product"), ("11-16s", "specs_cta")]
    if n == 4:
        return [("0-4s", "hook"), ("4-8s", "product"), ("8-12s", "specs"), ("12-16s", "cta")]
    # 5+
    return [
        ("0-3s", "hook"),
        ("3-6s", "lifestyle"),
        ("6-10s", "product"),
        ("10-13s", "specs"),
        ("13-16s", "cta"),
    ]


def _slide_hint_arc(n: int, hints: Optional[list] = None, slide_prompts: Optional[list] = None) -> list[str]:
    """Build ordered per-slide visual hints (EN), preserving upload order."""
    roles = list(CAROUSEL_ROLE_ARCS.get(n if n in CAROUSEL_ROLE_ARCS else 3, CAROUSEL_ROLE_ARCS[3]))
    while len(roles) < n:
        roles.append("content")
    out: list[str] = []
    hints = list(hints or [])
    sps = list(slide_prompts or [])
    generic = {
        "hook": "wide establishing lifestyle / environment with the pair readable",
        "lifestyle": "knees-down on-foot, exactly two feet FORWARD light walk",
        "product": "clean 3/4 product hero, slow push-in",
        "product_cta": "3/4 hero settling into calm hold",
        "specs": "macro midsole/outsole slow glide",
        "specs_cta": "macro detail then ease to calm hold",
        "cta": "calm flat-lay or side hold for ending",
        "content": "gentle educational footwear beat",
        "start": "product hero already in frame with camera-only push-in",
        "deepen": "closer orbit / tilt to sole detail",
        "end": "calm hold ending still",
    }
    for i in range(n):
        role = roles[i] if i < len(roles) else "content"
        h = ""
        if i < len(hints) and _clean(hints[i]):
            h = _clean(hints[i])
        elif i < len(sps) and _clean(sps[i]):
            # Take a short cue from existing slide prompt text (first ~140 chars, strip Create an image:)
            raw = _clean(sps[i])
            raw = raw.replace("Create an image:", "").strip()
            h = (raw[:160] + ("…" if len(raw) > 160 else "")).strip()
        else:
            # Generic arc by position
            if i == 0:
                h = "slide 1 hero — " + generic.get(role, generic["hook"])
            elif i == n - 1:
                h = f"slide {i+1} lifestyle/CTA close — " + generic.get(role, generic["cta"])
            else:
                h = f"slide {i+1} detail — " + generic.get(role, generic["product"])
        out.append(h)
    return out


def build_unified_grok_video_prompt(
    brand: str = "",
    model: str = "",
    colorway: str = "",
    specs: str = "",
    env: str = "",
    props: str = "",
    problem: str = "",
    watermark: str = "",
    appearance: str = "eu",
    goal: str = "auto",
    slide_hints: Optional[list] = None,
    slide_prompts: Optional[list] = None,
    slide_texts: Optional[list] = None,
    slide_count: int = 3,
    duration_s: int = 16,
    aspect: str = "9:16",
    lang: str = "el",
    topic: str = "",
    product_mode: bool = True,
    source: str = "slides",
    vibe: str = "",
) -> dict[str, Any]:
    """Build ONE continuous English Grok Video prompt (~16s) with timed beats inside.

    Returns dict: prompt_en, summary_el, howto_el, howto_en, slide_count, source, duration_hint.
    """
    try:
        n = int(slide_count)
    except (TypeError, ValueError):
        n = 3
    if slide_hints:
        n = max(n, len([h for h in slide_hints if _clean(h)]))
    if slide_texts:
        n = max(n, len(slide_texts))
    if n < 2:
        n = 2
    if n > 5:
        n = 5

    # Prefer explicit hints; else derive from slide_texts titles/bodies; else slide_prompts
    hints: list[str] = []
    if slide_hints:
        hints = [_clean(h) for h in slide_hints if _clean(h)]
    elif slide_texts:
        for item in slide_texts:
            if isinstance(item, dict):
                title = _clean(item.get("title"))
                body = _clean(item.get("body"))
                hints.append(" — ".join(x for x in (title, body) if x) or "story beat")
            else:
                hints.append(_clean(item) or "story beat")
    hints = _slide_hint_arc(n, hints=hints or None, slide_prompts=slide_prompts)

    windows = _time_windows(n)
    # Align window count to n
    if len(windows) != n:
        windows = _time_windows(n)[:n]

    pair = " ".join(x for x in (_clean(brand), _clean(model), _clean(colorway)) if x)
    scene = _env_hint(env, problem, goal)

    parts: list[str] = []
    parts.append(
        f"Photorealistic commercial video, {aspect} vertical, ONE continuous ~{duration_s}s shot/story "
        f"(not three separate ads). Generate once — timed segments below are beats INSIDE this single video."
    )
    parts.append(_safe_motion_rules())
    parts.append(_anatomy_video_clause())
    parts.append(_appearance_video_clause(appearance))
    parts.append(_no_chrome())
    parts.append(
        "Shoe lock every moment — never morph into a different pair; "
        "NEVER empty static shoes then jump to a runner; prefer product + camera motion "
        "(push-in, gentle orbit, slight tilt) or already-on-feet with exactly 2 feet FORWARD only "
        "(no reverse, no spins)."
    )

    if product_mode and (_clean(brand) or _clean(model)):
        parts.append(_shoe_lock(brand, model, colorway))
        parts.append(_specs_hint(specs).strip())
        parts.append(f"Setting family: {scene}.")
    else:
        topic_bit = _clean(topic) or "educational sneaker care / footwear tips"
        parts.append(
            f"Educational footwear story about: {topic_bit}. "
            "Generic authentic sneakers OK — soft trademark-safe; no Nike/Adidas logo inventing."
        )

    # Timed visual story through uploaded / slide frames in order
    beat_bits: list[str] = []
    for i, ((win, role), hint) in enumerate(zip(windows, hints), start=1):
        motion = _motion_for_role(
            role, brand=brand, model=model, colorway=colorway, product_mode=product_mode
        )
        is_final = i == n
        wm = _watermark_clause(watermark, final_beat=is_final)
        beat_bits.append(
            f"{win}: visual story of frame {i}/{n} — {hint}. {motion} {wm}"
        )
    parts.append(" ".join(beat_bits))
    parts.append(
        "Continuity as ONE continuous camera story flowing through these frames in order — "
        "same lighting family, same exact pair, cinematic, sharp, no morphing shoes, no UI chrome."
    )
    if _clean(watermark):
        parts.append("Watermark only in the final seconds if set; keep earlier frames clean.")
    else:
        parts.append("No watermark, no domain text on screen.")
    _music_extra = " ".join(x for x in ([_clean(topic)] + [_clean(h) for h in hints]) if x)
    parts.append(
        music_clause_for_scene(env, props, problem, vibe, _music_extra, story=True)
    )
    parts.append(VIDEO_AUDIO_NEGATIVES)
    parts.append(VIDEO_FINAL_CHECK)
    music_el = music_summary_for_scene(env, props, problem, vibe, _music_extra, lang="el")
    music_en = music_summary_for_scene(env, props, problem, vibe, _music_extra, lang="en")

    prompt_en = " ".join(p.strip() for p in parts if p and str(p).strip())

    if (lang or "el").lower() == "el":
        summary_el = (
            f"Ενιαίο ~{duration_s}s video ({n} καρέ σε σειρά). "
            f"Επικόλλησε μία φορά στο Grok Video → Generate ({aspect}). "
            f"Η ιστορία ρέει 1→{n} μέσα στο ίδιο prompt (timed beats). "
            f"{music_el}."
        )
    else:
        summary_el = (
            f"Unified ~{duration_s}s video ({n} frames in order). "
            f"Paste once into Grok Video → Generate ({aspect}). "
            f"Story flows 1→{n} inside one prompt (timed beats). "
            f"{music_en}."
        )

    return {
        "prompt_en": prompt_en,
        "summary_el": summary_el,
        "howto_el": UNIFIED_HOWTO_EL,
        "howto_en": UNIFIED_HOWTO_EN,
        "slide_count": n,
        "source": _clean(source) or "slides",
        "duration_hint": f"~{duration_s}s · {aspect}",
        "slide_hints": hints,
        "music_summary_el": music_el,
        "music_summary_en": music_en,
        "music_summary": music_el if (lang or "el").lower() == "el" else music_en,
    }


def format_unified_video_txt(
    unified: dict[str, Any],
    *,
    brand: str = "",
    model: str = "",
    colorway: str = "",
    topic: str = "",
) -> str:
    """Plain-text export for download / ZIP (video_unified.txt)."""
    if not isinstance(unified, dict):
        return ""
    lines = [
        "Sneakerness — Grok Video UNIFIED prompt (single Generate)",
        "How to use: paste the English prompt below once into Grok Video → Generate (~16s, 9:16).",
        "Do NOT Extend per beat — timed segments are inside this one prompt.",
        "",
    ]
    product = " ".join(x for x in (_clean(brand), _clean(model), _clean(colorway)) if x)
    if product:
        lines.append(f"Product: {product}")
    if _clean(topic):
        lines.append(f"Topic: {_clean(topic)}")
    lines.append(f"Duration: {unified.get('duration_hint') or '~16s · 9:16'}")
    lines.append(f"Slides: {unified.get('slide_count') or ''}")
    lines.append(f"Source: {unified.get('source') or ''}")
    if _clean(unified.get("music_summary_en")):
        lines.append(f"Audio — {_clean(unified.get('music_summary_en'))} (instrumental only, no voiceover)")
    lines.append(f"Howto: {unified.get('howto_en') or UNIFIED_HOWTO_EN}")
    lines.append("")
    lines.append("========== UNIFIED PROMPT (EN) ==========")
    lines.append("")
    lines.append(_clean(unified.get("prompt_en")))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def ensure_video_beats(
    existing: Any,
    **kwargs,
) -> dict[str, Any]:
    """Return existing video_beats dict if valid; else rebuild from kwargs."""
    if isinstance(existing, dict) and existing.get("beats"):
        return existing
    return build_grok_video_beats(**kwargs)
