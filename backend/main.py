import json
import os
import re
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="LearnForge API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_CHARS = 24_000
SUPPORTED_SUFFIXES = {".txt", ".md", ".text", ".pdf", ".docx"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCitation(StrictModel):
    excerpt: str = Field(description="A short exact quote from the uploaded material.")
    location: str = Field(description="A page number or section name; otherwise 'Uploaded material'.")


class Lesson(StrictModel):
    title: str
    summary: str
    duration_minutes: int = Field(ge=3, le=30)
    objectives: List[str] = Field(min_length=2, max_length=3)
    citation: SourceCitation


class QuizQuestion(StrictModel):
    question: str
    options: List[str] = Field(min_length=4, max_length=4)
    answer: int = Field(ge=0, le=3)
    explanation: str
    objective: str
    citation: SourceCitation


class Course(StrictModel):
    title: str
    description: str
    lessons: List[Lesson] = Field(min_length=3, max_length=3)
    quiz: List[QuizQuestion] = Field(min_length=4, max_length=4)


STOP_WORDS = {"about", "after", "also", "because", "between", "from", "have", "into", "more", "other", "their", "there", "these", "this", "that", "they", "with", "which", "will", "would", "your", "than", "then", "when", "where", "while", "were", "been", "being", "what", "does", "each"}


def short_text(value: str, length: int = 180) -> str:
    return re.sub(r"\s+", " ", value).strip()[:length].rstrip(" ,;:-")


def build_free_course(text: str, filename: str) -> Course:
    """A no-cost, source-grounded local fallback for the hackathon demo."""
    sentences = [short_text(item) for item in re.split(r"(?<=[.!?])\s+|\n+", text) if len(short_text(item)) > 45]
    if len(sentences) < 4:
        sentences = [short_text(line) for line in text.splitlines() if len(short_text(line)) > 20]
    sentences = (sentences + ["Review the uploaded material carefully."] * 4)[:12]
    words = re.findall(r"[A-Za-z]{5,}", text.lower())
    topics = [word.title() for word, _ in Counter(word for word in words if word not in STOP_WORDS).most_common(3)] or ["Key Ideas", "Core Concepts", "Practice"]
    title = Path(filename).stem.replace("_", " ").replace("-", " ").title() or "Learning Path"
    lessons = []
    for index, topic in enumerate(topics):
        source = sentences[min(index * 2, len(sentences) - 1)]
        lessons.append(Lesson(
            title=f"{index + 1}. {topic}",
            summary=source,
            duration_minutes=10 + index * 3,
            objectives=[f"Explain the main idea behind {topic}", f"Find evidence about {topic} in the material"],
            citation=SourceCitation(excerpt=source, location="Uploaded material"),
        ))
    questions = []
    for index in range(4):
        source = sentences[min(index + 1, len(sentences) - 1)]
        objective = lessons[index % len(lessons)].objectives[0]
        questions.append(QuizQuestion(
            question=f"Which statement is supported by the uploaded material about {topics[index % len(topics)]}?",
            options=[source, "The topic is unrelated to the uploaded material.", "The material says evidence is unnecessary.", "The material recommends skipping the topic."],
            answer=0,
            explanation="The first option is taken directly from the uploaded material.",
            objective=objective,
            citation=SourceCitation(excerpt=source, location="Uploaded material"),
        ))
    return Course(title=title, description="A free, source-grounded learning path created locally from your uploaded material.", lessons=lessons, quiz=questions)


def make_prompt(text: str, filename: str) -> str:
    return f"""You are LearnForge, a careful instructional designer. Create a beginner-friendly course using ONLY the uploaded learning material below. Do not invent facts. Return exactly the requested JSON structure. Create exactly 3 sequential lessons and exactly 4 multiple-choice quiz questions. Each lesson needs 2-3 measurable objectives. Each question must test a stated lesson objective, have exactly four plausible choices, and use a zero-based answer index. For every lesson and question, include a very short exact quote from the source as its citation excerpt. Use a useful page/section location if it appears in the material; otherwise use 'Uploaded material'.\n\nFilename: {filename}\n\nUPLOADED MATERIAL START\n{text}\nUPLOADED MATERIAL END"""


def generate_ai_course(text: str, filename: str) -> Course:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI is not configured yet. Add OPENAI_API_KEY to backend/.env and restart the server.")
    try:
        response = OpenAI(api_key=api_key).responses.create(
            model="gpt-4.1-mini",
            input=make_prompt(text, filename),
            # The app validates the returned JSON with the Course Pydantic model below.
            # JSON mode avoids provider-specific schema restrictions during a live demo.
            text={"format": {"type": "json_object"}},
            max_output_tokens=2400,
            store=False,
        )
        return Course.model_validate(json.loads(response.output_text))
    except Exception as error:
        if getattr(error, "status_code", None) == 429:
            return build_free_course(text, filename)
        raise HTTPException(status_code=502, detail=f"AI course generation failed: {error}") from error


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
    return {"status": "ok", "service": "learnforge-api", "ai_configured": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/api/courses/generate", response_model=Course)
async def generate_course(file: UploadFile = File(...)):
    filename = file.filename or "learning-material"
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Please upload a PDF, DOCX, Markdown, or text file.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="That file is empty. Please choose a file with readable text.")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Please use a file smaller than 8 MB for this demo.")
    try:
        text = (await extract_text(file, raw)).strip()
    except Exception as error:
        raise HTTPException(status_code=400, detail="LearnForge could not read that file. Try a text-based PDF or DOCX.") from error
    if len(text) < 120:
        raise HTTPException(status_code=400, detail="Not enough readable text was found. Scanned PDFs need OCR before upload.")
    return generate_ai_course(text[:MAX_SOURCE_CHARS], filename)
