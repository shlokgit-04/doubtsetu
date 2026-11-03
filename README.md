# DoubtSetu

**Snap your doubt, get the concept.** An AI study buddy for school students (class 6-12) that explains any school question step by step in **Marathi, Hindi or English**, then builds a practice quiz from the same topic so the doubt actually sticks.

Built for the [STEM2Connect AI Hackathon](https://stem2connect-online-hackathon.devpost.com/).

## The problem
Students in India often study after school hours when no teacher is around. Most AI tutors answer only in English, and textbook doubts in Marathi or Hindi go unasked. DoubtSetu meets the student in their own language, solves the doubt step by step, and turns the same topic into a 3-question quiz, because a doubt is only cleared when you can answer a question on it.

## How it works
1. The student types a doubt or attaches a photo of a textbook page / worksheet / their notebook.
2. The photo and question go to the Flask backend, which calls **Google Gemini 2.0 Flash** (free tier) with a structured prompt.
3. Gemini returns structured JSON: the underlying concept, 3-6 numbered solving steps, one similar practice example with its answer, and 3 multiple-choice quiz items on the same topic.
4. The UI shows the answer in the chosen language and makes the quiz interactive with instant right/wrong feedback and a one-line reason for each answer.

## Which AI tech is used (and why)
- **Google Gemini 2.0 Flash** via the official `generativelanguage.googleapis.com` REST API, with `responseMimeType: application/json` so the tutor's output is always structured and parseable.
- **Multimodal input**: textbook photos are sent to Gemini as `inline_data` images, so a student can just snap their notebook instead of typing.
- **Prompt engineering**: a fixed role prompt ("friendly tutor for class 6-12, short warm sentences") plus an explicit JSON schema keeps answers consistent, student-readable and language-correct.
- A **demo mode** fallback: if the server key is absent, the app shows one built-in sample answer clearly labelled "Demo mode", so the interface is never empty.

## Try it
- Live app: https://doubtsetu-xm13.onrender.com
- Repo: https://github.com/shlokgit-04/doubtsetu

## Run locally
```
pip install -r requirements.txt
export GEMINI_API_KEY=your_key   # optional; without it the app runs in demo mode
python app.py
```

## Stack
Python (Flask) + Gunicorn · vanilla HTML/CSS/JS frontend · Google Gemini 2.0 Flash API · deployed free on Render.

## Honest limits
AI answers can be wrong; the UI says so and asks students to double-check with their teacher. The free Gemini tier has rate limits, so a burst of users may see a retry message.
