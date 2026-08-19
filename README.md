# 👟 Sneakerness Engine & Ad Studio

An end-to-end, AI-powered e-commerce curation and ad creative engine built with **Streamlit** and **Google Gemini (2.0 / 1.5 Flash)**. 

Designed specifically for footwear curators, dropshippers, and digital marketers, **Sneakerness Engine** automates product feature extraction, background aesthetic alignment, multi-slide carousel framing, and soft-discovery copy generation for Meta Ads and TikTok Photo Mode.

---

## ✨ Key Features

* **👁️ Multimodal Visual Recognition:** Analyzes sneaker product images (`.jpg`, `.png`, `.webp`) to automatically detect brand, exact model, colorway, material specs, and optimal lifestyle/architectural scene pairings.
* **🍌 Nano Banana & Midjourney Ad Prompts:** Generates 3-part seamless vertical ad layout prompts designed to eliminate black bars, hard edges, and awkward text placement.
* **🎠 3-Slide Carousel Studio:** Creates structured narrative frames (Slide 1: Problem/Hook ➔ Slide 2: Hero Product Showcase ➔ Slide 3: Macro Specs & Comfort Features) tailored for TikTok Photo Mode and Instagram Carousels.
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
