# LearnForge v1.0.2

## What changed

- Refreshed the homepage copy so the product value is clear on first load.
- Added a page description for better sharing and browser previews.
- Simplified the upload experience and button labels.
- Kept PDF, DOCX, Markdown, and TXT support unchanged.
- Kept source citations, lesson views, quiz scoring, and the local fallback generator unchanged.
- Updated the Windows setup instructions to work when PowerShell blocks activation scripts.

## Run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/`.
