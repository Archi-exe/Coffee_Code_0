# LearnForge

AI-powered LMS prototype for turning educational material into structured learning paths.

## Run locally

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

This setup does not require PowerShell script activation. If activation is preferred, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, then run `.` + `\\.venv\\Scripts\\Activate.ps1` in PowerShell.

Open `http://127.0.0.1:8000/` in your browser. The FastAPI server serves the frontend, so do not open `frontend/index.html` directly and do not start a second frontend server.

The app accepts `.txt`, `.md`, `.pdf`, and `.docx` files. It uses the local source-grounded fallback by default. To enable AI generation, create `backend/.env` from `backend/.env.example` and add either an `OPENAI_API_KEY` or `GEMINI_API_KEY`.

Check the API at `http://127.0.0.1:8000/docs` and the health endpoint at `http://127.0.0.1:8000/health`.

## Product direction

The demo is intentionally built as a vertical slice: material ingestion → course generation → lesson outline. The deterministic generator in `backend/main.py` is the seam to replace with an LLM pipeline that extracts chunks, creates learning objectives, generates assessments, and stores source citations.

## Next milestones

1. Improve provider selection and structured JSON validation.
2. Add persistent course records, spaced-repetition review, and learner progress.
3. Add teacher controls for editing, approving, and sharing generated courses.
