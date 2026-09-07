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
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI(title="LearnForge API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_CHARS = 24_000
SUPPORTED_SUFFIXES = {".txt", ".md", ".text", ".pdf", ".docx"}
FRONTEND_PAGE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def frontend():
    """Serve the demo and API from one local server."""
    return FileResponse(FRONTEND_PAGE)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCitation(StrictModel):
    excerpt: str = Field(description="A short exact quote from the uploaded material.")
    location: str = Field(description="A page number or section name; otherwise 'Uploaded material'.")


class Lesson(StrictModel):
    title: str
    summary: str
    content: str = Field(description="A short, source-grounded lesson that teaches the topic in 2-3 beginner-friendly paragraphs.")
    duration_minutes: int = Field(ge=1, le=30)
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


def passage_for_topic(topic: str, sentences: List[str], fallback_start: int) -> List[str]:
    """Select the clearest source sentences for one topic without inventing facts."""
    topic_pattern = re.compile(rf"\b{re.escape(topic)}\w*\b", re.IGNORECASE)
    matches = [sentence for sentence in sentences if topic_pattern.search(sentence)]
    selected = matches[:3]
    if len(selected) < 3:
        start = fallback_start % len(sentences)
        for offset in range(len(sentences)):
            sentence = sentences[(start + offset) % len(sentences)]
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) == 3:
                break
    return selected


def reading_minutes(text: str) -> int:
    return max(1, round(len(re.findall(r"\b\w+\b", text)) / 160))


def build_free_course(text: str, filename: str) -> Course:
    """A no-cost, source-grounded local fallback for the hackathon demo."""
    sentences = [short_text(item) for item in re.split(r"(?<=[.!?])\s+|\n+", text) if len(short_text(item)) > 45]
    if len(sentences) < 4:
        sentences = [short_text(line) for line in text.splitlines() if len(short_text(line)) > 20]
    sentences = sentences or ["Review the uploaded material carefully."]
    words = re.findall(r"[A-Za-z]{5,}", text.lower())
    topics = [word.title() for word, _ in Counter(word for word in words if word not in STOP_WORDS).most_common(3)] or ["Key Ideas", "Core Concepts", "Practice"]
    title = Path(filename).stem.replace("_", " ").replace("-", " ").title() or "Learning Path"
    lessons = []
    for index, topic in enumerate(topics):
        key_sentences = passage_for_topic(topic, sentences, index * 3)
        source = short_text(key_sentences[0])
        content = "\n\n".join(
            [f"Key idea: {key_sentences[0]}"]
            + [f"Important detail: {sentence}" for sentence in key_sentences[1:]]
        )
        lessons.append(Lesson(
            title=f"{index + 1}. {topic}",
            summary=f"A focused summary of the main ideas about {topic}.",
            content=content,
            duration_minutes=reading_minutes(content),
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
    return f"""You are LearnForge, an excellent school teacher who turns difficult study material into simple, accurate lessons.

Use ONLY the uploaded material. Do not invent facts. Return only valid JSON matching the requested course structure.

Create exactly 3 lessons in a logical learning order and exactly 4 multiple-choice quiz questions. Every lesson must have:
- a specific, human-friendly title;
- a one-sentence summary;
- `content`: 2 to 4 short, polished paragraphs in very simple English. Explain ideas clearly, connect facts, and avoid copying raw textbook sentences or fragments;
- 2 or 3 measurable objectives;
- a short exact source quote and location.

Every quiz question must test a lesson objective, have exactly 4 plausible options, a zero-based answer index, a short explanation, and a source citation. Do not mention that you are an AI.

Filename: {filename}

UPLOADED MATERIAL START
{text}
UPLOADED MATERIAL END"""


def set_reading_times(course: Course) -> Course:
    for lesson in course.lessons:
        lesson.duration_minutes = reading_minutes(lesson.content)
    return course


def generate_gemini_course(text: str, filename: str) -> Course:
    """Create a polished course with Gemini when the user has configured its API key."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=make_prompt(text, filename),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=5000,
        ),
    )
    return set_reading_times(Course.model_validate_json(response.text))


def generate_openai_course(text: str, filename: str) -> Course:
    api_key = os.getenv("OPENAI_API_KEY")
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
        return set_reading_times(Course.model_validate(json.loads(response.output_text)))
    except Exception as error:
        raise RuntimeError("OpenAI course generation failed") from error


def generate_ai_course(text: str, filename: str) -> Course:
    if os.getenv("GEMINI_API_KEY"):
        try:
            return generate_gemini_course(text, filename)
        except Exception as error:
            print(f"Gemini course generation failed; using fallback: {error}")
    if os.getenv("OPENAI_API_KEY"):
        try:
            return generate_openai_course(text, filename)
        except Exception as error:
            print(f"OpenAI course generation failed; using fallback: {error}")
    return build_free_course(text, filename)


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
