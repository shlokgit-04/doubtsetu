import base64
import json
import os
import re

import requests
import time
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-3.8-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % MODEL

LANGS = {"en": "simple English", "hi": "simple Hindi (Devanagari script)", "mr": "simple Marathi (Devanagari script)"}

PROMPT = """You are DoubtSetu, a friendly tutor for school students of class 6-12 in India.
A student sends a doubt, sometimes with a photo of a textbook page, worksheet or their own notebook.
Explain and solve it in {language}. Use short, warm, encouraging sentences a school student can follow.

Return ONLY valid JSON with exactly these keys:
{{
  "concept": "2-3 sentence explanation of the underlying concept",
  "steps": ["step 1", "step 2", "..."],
  "example": "one short similar practice example with its answer",
  "quiz": [
    {{"question": "...", "options": ["...","...","...","..."], "answer_index": 0, "why": "one-line reason"}}
  ]
}}
The steps array holds 3 to 6 steps that actually solve the question. The quiz array holds exactly 3 items on the same topic, each options array has exactly 4 strings, answer_index is 0-3. No markdown fences, no text outside the JSON.

Student question: {question}
"""

DEMO = {
    "concept": "Demo mode: the live AI tutor needs its Gemini key on this server. Here is a built-in sample so you can see how DoubtSetu answers.",
    "steps": [
        "A right triangle has one 90-degree angle. The two shorter sides are a and b, the longest side (hypotenuse) is c.",
        "The Pythagorean theorem says: a² + b² = c².",
        "Put in the numbers: 3² + 4² = 9 + 16 = 25.",
        "So c² = 25, which means c = 5.",
    ],
    "example": "Try it: legs 6 and 8. Answer: hypotenuse = 10.",
    "quiz": [
        {"question": "If a = 5 and b = 12, what is c?", "options": ["13", "15", "17", "60"], "answer_index": 0, "why": "25 + 144 = 169 = 13²."},
        {"question": "Which side is always the longest in a right triangle?", "options": ["The hypotenuse", "Side a", "Side b", "All equal"], "answer_index": 0, "why": "The hypotenuse is opposite the right angle."},
        {"question": "a² + b² equals...", "options": ["c²", "c", "2c", "ab"], "answer_index": 0, "why": "That is the Pythagorean theorem."},
    ],
}


def _clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def call_gemini(question, lang, image_b64=None, image_mime=None):
    parts = [{"text": PROMPT.format(language=LANGS.get(lang, LANGS["en"]), question=question or "(see the photo I sent)")}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": image_mime or "image/jpeg", "data": image_b64}})
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048, "responseMimeType": "application/json"},
    }
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers={"x-goog-api-key": GEMINI_KEY}, json=payload, timeout=60)
        except requests.RequestException as e:
            app.logger.error('gemini network error attempt %s: %s', attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code in (429, 500, 503) and attempt < 2:
            app.logger.warning('gemini http %s on attempt %s, retrying', resp.status_code, attempt + 1)
            time.sleep(2 * (attempt + 1))
            continue
        break
    if not resp.ok:
        app.logger.error('gemini http %s: %s', resp.status_code, resp.text[:400])
        resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(_clean_json(text))


@app.route("/")
def index():
    return render_template("index.html", has_key=bool(GEMINI_KEY))


@app.route("/api/solve", methods=["POST"])
def solve():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    lang = body.get("language", "en")
    image_b64 = body.get("image")
    if not question and not image_b64:
        return jsonify({"error": "Type a doubt or attach a photo first."}), 400
    if len(question) > 4000:
        return jsonify({"error": "Question too long (4000 characters max)."}), 400
    if not GEMINI_KEY:
        demo = dict(DEMO)
        demo["demo_mode"] = True
        return jsonify(demo)
    try:
        result = call_gemini(question, lang, image_b64, body.get("image_mime"))
        result["demo_mode"] = False
        return jsonify(result)
    except Exception:
        app.logger.exception("gemini call failed")
        return jsonify({"error": "The AI tutor could not answer just now. Please try again in a minute."}), 502


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "model": MODEL, "ai_ready": bool(GEMINI_KEY)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
