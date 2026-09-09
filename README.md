# LearnForge

LearnForge is an AI-powered learning management system and course builder. It turns textbooks, PDFs, DOCX files, Markdown, and notes into structured lessons, learning objectives, source citations, and knowledge checks.

The project is designed for the Resonance 1.0 hackathon and ships as a local-first FastAPI application with an optional OpenAI or Gemini generation layer.

## Features

- Upload PDF, DOCX, Markdown, and plain-text study material
- Generate focused lessons with objectives and source citations
- Generate a multiple-choice knowledge check
- Open individual lessons and review suggested next steps
- Run without an API key using the local source-grounded fallback
- Serve the frontend and API from one local server

## Prerequisites

- Windows
- Python 3.11 or newer
- Internet access during installation
- An OpenAI or Gemini API key only if provider-powered generation is needed

```powershell
python --version
```

## Quick start on Windows PowerShell

From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

This setup does not activate `.venv`, so it works when PowerShell blocks `.ps1` scripts. If you prefer activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Do not open `frontend/index.html` directly or start a second frontend server.

## Optional AI configuration

The app works without API keys. To enable provider-powered generation, copy `backend/.env.example` to `backend/.env`, add either `OPENAI_API_KEY` or `GEMINI_API_KEY`, and restart the server. Keep `.env` private.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Serve the LearnForge web app |
| `GET /health` | Check server status and AI configuration |
| `POST /api/courses/generate` | Upload material and generate a course |
| `/docs` | OpenAPI documentation |

## Supported files and limits

- Extensions: `.pdf`, `.docx`, `.md`, `.markdown`, `.txt`, `.text`
- Maximum upload size: 8 MB
- PDFs must contain selectable text. Scanned PDFs need OCR first.

## Troubleshooting

### PowerShell says scripts are disabled

Use the activation-free commands above, or run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the current terminal.

### `uvicorn` is not recognized

Run `.venv\Scripts\python.exe -m uvicorn main:app --reload`.

### Port 8000 is already in use

Stop the existing server with `Ctrl+C`, or run `.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001` and open `http://127.0.0.1:8001/`.

### The upload returns a readable-text error

Use a text-based PDF, DOCX, Markdown, or TXT file. Scanned PDFs need OCR first.

## Project structure

```text
backend/main.py          FastAPI application and course-generation pipeline
backend/requirements.txt Python dependencies
backend/.env.example     Optional provider configuration template
frontend/index.html      Browser interface served by FastAPI
data/                    Sample project data
render.yaml              Render deployment configuration
RELEASE_NOTES.md         Release history
```

## Deployment

`render.yaml` contains the Render deployment configuration. For production use, add authentication, persistent storage, rate limiting, provider cost controls, and server-side validation for uploaded content.

## Current release

The current tagged release is [`v1.0.2`](https://github.com/Archi-exe/Coffee_Code_0/releases/tag/v1.0.2). See [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Roadmap

1. Improve provider selection and structured JSON validation.
2. Add persistent course records, spaced-repetition review, and learner progress.
3. Add teacher controls for editing, approving, and sharing courses.
4. Implement an Event Handler.
5. Add API keys options.
6. Implement User database and login/signup methods
   
## License

No license has been declared yet. Add a `LICENSE` file before distributing the project outside the hackathon.
