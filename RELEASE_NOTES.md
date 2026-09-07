# Release notes

## v1.0.2

Current tagged release.

### Highlights

- Refreshed the homepage copy and first-run experience.
- Added browser description metadata for cleaner sharing and previews.
- Clarified the upload flow for PDF, DOCX, Markdown, and TXT files.
- Kept lesson views, source citations, quiz scoring, and local fallback generation intact.
- Added PowerShell-safe Windows setup instructions.

### Installation

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/`.

## v1.0.1

- Removed a personal local filesystem path from the README.
- Added Windows setup guidance for PowerShell execution-policy restrictions.

## v1.0.0

- Initial public release tag for the LearnForge hackathon prototype.
- PDF, DOCX, Markdown, and TXT ingestion.
- Structured lesson and quiz generation.
- FastAPI backend with a browser-based frontend.
