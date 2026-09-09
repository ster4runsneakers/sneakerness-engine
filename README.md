# 👟 Sneakerness Engine & Ad Studio

An end-to-end, AI-powered e-commerce curation and ad creative engine built with **Streamlit** and **Google Gemini (2.0 / 1.5 Flash)**. 

Designed specifically for footwear curators, dropshippers, and digital marketers, **Sneakerness Engine** automates product feature extraction, background aesthetic alignment, multi-slide carousel framing, and soft-discovery copy generation for Meta Ads and TikTok Photo Mode.

---

## ✨ Key Features

* **👁️ Multimodal Visual Recognition:** Analyzes sneaker product images (`.jpg`, `.png`, `.webp`) to automatically detect brand, exact model, colorway, material specs, and optimal lifestyle/architectural scene pairings.
* **🍌 Nano Banana & Midjourney Ad Prompts:** Generates 3-part seamless vertical ad layout prompts designed to eliminate black bars, hard edges, and awkward text placement.
* **🎠 Carousel Studio (2–5 slides):** Choose slide count (default 3). Story arcs: 2 = Hook → Product+CTA; 3 = Hook → Product → Specs+CTA; 4 = Hook → Product → Specs → Soft CTA; 5 = Hook → Lifestyle → Product → Specs → Soft CTA. Tailored for TikTok Photo Mode and Instagram Carousels.
* **✍️ Soft-Discovery Copywriting:** Drafts high-converting, non-aggressive ad copy and social captions focusing on posture support, daily comfort, and urban lifestyle discovery (No hard-sell spam).
* **🧹 Session State Management:** Auto-clears and overwrites previous image payloads to ensure clean multi-product workflow processing without session bloat.

---

## 🛠️ Tech Stack

* **Frontend / UI:** [Streamlit](https://streamlit.io/)
* **AI Engine:** [Google GenAI SDK](https://github.com/google-gemini/deprecations) (`gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`)
* **Environment:** Python 3.10+
* **Image Processing:** Pillow (`PIL`)
* **Environment Configuration:** `python-dotenv`

---

## 🚀 Quickstart Guide

### 1. Clone the repository
```bash
git clone [https://github.com/ster4runsneakers/sneakerness-engine.git](https://github.com/ster4runsneakers/sneakerness-engine.git)
cd sneakerness-engine

## Ιστορικό / Product History

* After **Generate Content Pack**, product fields, prompts, captions, and the shoe image are saved under `data/product_history.json` (images in `data/history_images/`).
* Use the sidebar **Ιστορικό / History** to reload a past product into the form or delete it.


## Language / Γλώσσα

* Use the sidebar **Language / Γλώσσα** toggle (**English** / **Ελληνικά**) to switch UI labels and the language of AI-generated ad copy, captions, hooks, and slide texts. Choice is stored in the Streamlit session only.

## Carousel slide count

* When **Ad Format** is the carousel option, use **Carousel slides / Αριθμός slides** to pick **2, 3, 4, or 5** (default **3**). The app generates that many Nano Banana prompts and stores `slide_count` plus `slide1_prompt`…`slide5_prompt` in product history (unused slides saved as empty strings).


## Additive extras (MON)

### A — Goal / story templates
* Expander-style **Story goal / angle** select: Auto, Comfort, Wide fit, Style, Rain care (EN/EL labels).
* Auto suggests a goal from specs (e.g. cushion → Comfort); you can override.
* The chosen goal is passed into caption/hook generation (`safe_generate_ad_copy`) as a soft-discovery angle and stored as `goal` on history entries.

### B — Weekly insights
* Sidebar **Weekly insights** reads `data/weekly_insights.json` (seed included; no scraper required).
* **Use this insight** stores the selection in session and biases the next Generate captions.
* Optional research scripts under `research/` are left as-is and are not required to run the UI.

### C — One-click export pack (ZIP)
* After Generate (and when a history pack is loaded): **Download pack (ZIP)** with `captions_meta.txt`, `captions_tiktok.txt`, `prompts.txt`, and `meta.json` (brand, model, colorway, goal, lang, aspect, slide_count, specs).
* Export only — does **not** auto-post to Instagram. Uses stdlib `zipfile` + `io.BytesIO`.
