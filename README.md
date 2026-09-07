# LearnForge

AI-powered LMS prototype for turning educational material into structured learning paths.

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `frontend/index.html` in a browser. Upload a `.txt`, `.md`, `.pdf`, or `.docx` file and generate a course outline plus interactive knowledge check.

## Product direction

The demo is intentionally built as a vertical slice: material ingestion → course generation → lesson outline. The deterministic generator in `backend/main.py` is the seam to replace with an LLM pipeline that extracts chunks, creates learning objectives, generates assessments, and stores source citations.

## Next milestones

1. Replace the fallback generator with an LLM provider plus structured JSON validation.
2. Add persistent course records, spaced-repetition review, and learner progress.
3. Add teacher controls for editing, approving, and sharing generated courses.
