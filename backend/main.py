from pathlib import Path
from typing import List
from io import BytesIO

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LearnForge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    # Local hackathon prototype: allow the static frontend and localhost dev servers.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Lesson(BaseModel):
    title: str
    summary: str
    duration_minutes: int
    objectives: List[str]


class Course(BaseModel):
    title: str
    description: str
    lessons: List[Lesson]
    quiz: List["QuizQuestion"]


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: int
    explanation: str


def build_demo_course(text: str, filename: str) -> Course:
    """Deterministic fallback used until an LLM provider is connected."""
    title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    topic = text.strip().split("\n")[0][:90] if text.strip() else title
    return Course(
        title=title or "Untitled learning path",
        description=f"A focused learning path generated from {filename}.",
        lessons=[
            Lesson(title=f"What is {topic}?", summary="Build the essential mental model and vocabulary.", duration_minutes=12, objectives=["Define the key ideas", "Recognize the core vocabulary"]),
            Lesson(title="How the ideas connect", summary="Use examples to connect concepts and identify patterns.", duration_minutes=15, objectives=["Explain the relationships between ideas", "Apply the model to a new example"]),
            Lesson(title="Practice and check understanding", summary="Retrieve the most important ideas with a short assessment.", duration_minutes=10, objectives=["Solve a representative problem", "Identify what to review next"]),
        ],
        quiz=[
            QuizQuestion(question=f"Which statement best describes {topic}?", options=["A central subject in this learning material", "An unrelated topic", "A file format", "A user interface element"], answer=0, explanation="The uploaded material is organized around this subject."),
            QuizQuestion(question="What is the best way to learn the material?", options=["Only reread it once", "Connect ideas and practice retrieval", "Skip the examples", "Memorize without understanding"], answer=1, explanation="Connecting ideas and retrieval practice improve understanding."),
        ],
    )


async def extract_text(file: UploadFile, raw: bytes) -> str:
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
    if name.endswith(".docx"):
        from docx import Document
        return "\n".join(paragraph.text for paragraph in Document(BytesIO(raw)).paragraphs)
    return raw.decode("utf-8", errors="ignore")


@app.get("/health")
def health():
    return {"status": "ok", "service": "learnforge-api"}


@app.post("/api/courses/generate", response_model=Course)
async def generate_course(file: UploadFile = File(...)):
    raw = await file.read()
    text = await extract_text(file, raw)
    return build_demo_course(text, file.filename or "learning-material")
