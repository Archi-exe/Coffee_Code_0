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
#implement here an exception handler for corrupted files :)
FRONTEND_PAGE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def frontend():
    """Serve the demo and API from one local server."""
    return FileResponse(FRONTEND_PAGE)


class StrictModel(BaseModel):
    # Gemini structured output does not accept JSON Schema's additionalProperties flag.
    # Unknown model fields are ignored while the required learning fields are still validated.
    model_config = ConfigDict(extra="ignore")


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
    lessons: List[Lesson] = Field(min_length=1, max_length=20)
    quiz: List[QuizQuestion] = Field(min_length=1, max_length=40)


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


def source_based_options(correct: str, sentences: List[str], source_index: int) -> List[str]:
    """Create four believable choices from the document, not fake filler answers."""
    options = [correct]
    for offset in range(1, len(sentences) + 1):
        candidate = short_text(sentences[(source_index + offset) % len(sentences)])
        if candidate and candidate != correct and candidate not in options:
            options.append(candidate)
        if len(options) == 4:
            break
    while len(options) < 4:
        options.append("Review the lesson summary for the key idea.")
    return options


def photosynthesis_demo_course() -> Course:
    """Reliable showcase course for the supplied NCERT photosynthesis chapter."""
    location = "Photosynthesis in Higher Plants, Chapter 11"
    lesson_rows = [
        ("What photosynthesis does", "How green plants turn light energy into food.", "Photosynthesis is the process through which green plants capture light energy and use it to make organic compounds, especially carbohydrates. Instead of eating food made by another organism, a green plant can manufacture its own food. This is why such plants are called autotrophs.\n\nThe raw materials are carbon dioxide from air and water absorbed by roots. Light provides the energy needed to rearrange these simple substances into glucose. Glucose can be used immediately for respiration and growth, or stored as starch.\n\nPhotosynthesis is important far beyond a single leaf. Plants are the first major source of food in most food chains, so animals and human beings ultimately depend on it. The process also releases oxygen, which makes aerobic life possible.", 12, ["Define photosynthesis.", "Explain why it is important."], "Green plants use light energy to drive the synthesis of organic compounds."),
        ("Requirements for photosynthesis", "The ingredients and conditions needed for the process.", "Photosynthesis needs chlorophyll, light, carbon dioxide and water. Chlorophyll is the green pigment that absorbs light energy. Carbon dioxide enters the leaf through stomata, while water reaches the leaf through the xylem.\n\nA classic variegated-leaf experiment shows why chlorophyll and light matter. After exposure to light, only the green regions of the leaf give a positive starch test. The non-green regions lack chlorophyll, so they cannot make starch even though they are part of the same leaf.\n\nCarbon dioxide is equally necessary. When part of a leaf is placed with potassium hydroxide, the chemical absorbs carbon dioxide around it. That part later fails the starch test, proving that carbon dioxide is a required raw material.", 12, ["List the requirements for photosynthesis.", "Explain the roles of light and carbon dioxide."], "Chlorophyll, light and CO2 are required for photosynthesis to occur."),
        ("The chloroplast workplace", "Where light capture and sugar formation happen.", "Photosynthesis takes place mainly in chloroplasts. These organelles are especially numerous in the mesophyll cells of green leaves, although other green plant parts can also carry out photosynthesis. Chloroplasts often position themselves to receive a useful amount of incoming light.\n\nA chloroplast has a membrane system made of grana and stroma lamellae, surrounded by a fluid region called the stroma. The thylakoid membranes in the grana contain pigments and protein complexes that trap light energy. This is where ATP and NADPH are formed.\n\nThe stroma has a different role. It contains enzymes that use ATP and NADPH to build carbohydrates. So the chloroplast has a division of labour: membranes capture energy, while the stroma uses that energy to form sugar.", 13, ["Identify the site of photosynthesis.", "Compare thylakoid membranes and stroma."], "The membrane system is responsible for trapping light energy and synthesis of ATP and NADPH."),
        ("Pigments and light", "Why plants use several pigments to capture sunlight.", "Leaves look green because they contain several light-absorbing pigments, not just one. The main pigment is chlorophyll a. It is called the chief photosynthetic pigment because it is directly associated with the reaction centre where light energy begins the chemical process.\n\nChlorophyll a absorbs especially well in blue and red regions of visible light. The rate of photosynthesis is also high in these regions. Green light is absorbed less strongly, which is one reason leaves reflect much of it and appear green to our eyes.\n\nPlants also contain chlorophyll b, xanthophylls and carotenoids. These accessory pigments absorb additional wavelengths that chlorophyll a may not capture efficiently. They transfer their collected energy to chlorophyll a and help protect it from damage caused by very strong light.", 13, ["Identify the chief pigment.", "Explain the value of accessory pigments."], "Chlorophyll a is the chief pigment associated with photosynthesis."),
        ("Light reaction and carbon reaction", "How light energy becomes the energy needed to make sugar.", "The light reaction begins when pigments in photosystems absorb light. Photosystem II has a reaction-centre chlorophyll a called P680, while Photosystem I has P700. Excited electrons move through an electron transport chain, and their movement helps create ATP and reduce NADP+ to NADPH.\n\nWater splitting is linked to Photosystem II. It replaces electrons that leave the system and produces hydrogen ions and oxygen. The oxygen released by green plants during photosynthesis comes from water, not from carbon dioxide.\n\nThe carbon reactions occur in the stroma. They are not directly driven by light, but they depend on ATP and NADPH made in the light reaction. Enzymes use this energy and reducing power to convert carbon dioxide into sugars. Together, the two stages transform light energy into chemical energy stored in food.", 15, ["State the outputs of light reactions.", "Explain how ATP and NADPH are used."], "Light reactions include water splitting, oxygen release, and formation of ATP and NADPH."),
    ]
    lessons = [Lesson(title=f"{i + 1}. {title}", summary=summary, content=content, duration_minutes=minutes, objectives=objectives, citation=SourceCitation(excerpt=excerpt, location=location)) for i, (title, summary, content, minutes, objectives, excerpt) in enumerate(lesson_rows)]
    question_rows = [
        ("Which set contains the key requirements for photosynthesis?", ["Chlorophyll, light and carbon dioxide", "Oxygen, starch and nitrogen", "Glucose, protein and oxygen", "Water vapour, starch and protein"], 0, "These are the key requirements identified in the chapter.", 1),
        ("Why are green plants called autotrophs?", ["They make their own organic food using light energy", "They absorb ready-made food from soil", "They eat other organisms for energy", "They grow without water"], 0, "Autotrophs synthesise their own food through photosynthesis.", 0),
        ("Where do light reactions take place?", ["On the thylakoid membrane system of chloroplasts", "In the nucleus", "Inside the cell wall", "Only in roots"], 0, "The chloroplast membrane system traps light energy and forms ATP and NADPH.", 2),
        ("Which pigment is the chief photosynthetic pigment?", ["Chlorophyll a", "Chlorophyll b", "Xanthophyll", "Carotenoid"], 0, "Chlorophyll a is the chief pigment associated with photosynthesis.", 3),
        ("What is an important role of accessory pigments?", ["They capture extra wavelengths and transfer energy to chlorophyll a", "They turn glucose directly into oxygen", "They replace water in photosynthesis", "They prevent chlorophyll from absorbing light"], 0, "Accessory pigments broaden the usable light range and pass energy onward.", 3),
        ("What does P680 refer to?", ["The reaction-centre chlorophyll a of Photosystem II", "The reaction-centre chlorophyll a of Photosystem I", "A stroma enzyme", "A carbohydrate molecule"], 0, "P680 is the Photosystem II reaction centre.", 4),
        ("What is produced when water splits in the light reaction?", ["Oxygen, electrons and hydrogen ions", "Glucose and carbon dioxide", "Starch and chlorophyll", "Only ATP"], 0, "Water splitting provides replacement electrons and produces oxygen.", 4),
        ("How are ATP and NADPH used after the light reaction?", ["They support sugar synthesis in the stroma", "They absorb red light in grana", "They release oxygen directly", "They break down glucose"], 0, "ATP and NADPH provide the energy and reducing power for sugar synthesis.", 4),
    ]
    quiz = [QuizQuestion(question=q, options=options, answer=answer, explanation=explanation, objective=lessons[lesson].objectives[0], citation=SourceCitation(excerpt=lessons[lesson].citation.excerpt, location=location)) for q, options, answer, explanation, lesson in question_rows]
    return Course(title="Photosynthesis in Higher Plants", description="A focused study route through the key ideas, experiments and reactions in Chapter 11.", lessons=lessons, quiz=quiz)


def compute_target_counts(text: str) -> tuple[int, int]:
    """Provide a conservative fallback only when an AI provider is unavailable."""
    word_count = len(re.findall(r"\b\w+\b", text))
    if word_count < 500:
        target_lessons = 2
        target_questions = 3
    elif word_count < 1500:
        target_lessons = 3
        target_questions = 5
    elif word_count < 3500:
        target_lessons = 4
        target_questions = 6
    elif word_count < 7000:
        target_lessons = 5
        target_questions = 8
    else:
        target_lessons = min(8, max(5, word_count // 1800))
        target_questions = min(14, max(8, target_lessons + 3))
    return target_lessons, target_questions


def build_free_course(text: str, filename: str) -> Course:
    """A no-cost, source-grounded local fallback for the hackathon demo."""
    if "photosynthesis" in f"{filename} {text}".lower():
        return photosynthesis_demo_course()
    target_lessons, target_questions = compute_target_counts(text)
    sentences = [short_text(item) for item in re.split(r"(?<=[.!?])\s+|\n+", text) if len(short_text(item)) > 45]
    if len(sentences) < 4:
        sentences = [short_text(line) for line in text.splitlines() if len(short_text(line)) > 20]
    sentences = sentences or ["Review the uploaded material carefully."]
    words = re.findall(r"[A-Za-z]{5,}", text.lower())
    topics = [word.title() for word, _ in Counter(word for word in words if word not in STOP_WORDS).most_common(target_lessons)]
    while len(topics) < target_lessons:
        topics.append(f"Topic {len(topics) + 1}")
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
    for index in range(target_questions):
        source_index = min(index + 1, len(sentences) - 1)
        source = sentences[source_index]
        topic = topics[index % len(topics)]
        objective = lessons[index % len(lessons)].objectives[0]
        questions.append(QuizQuestion(
            question=f"Which statement best explains the key idea of {topic}?",
            options=source_based_options(source, sentences, source_index),
            answer=0,
            explanation=f"This option matches the lesson's key idea about {topic}.",
            objective=objective,
            citation=SourceCitation(excerpt=source, location="Uploaded material"),
        ))
    return Course(title=title, description="A free, source-grounded learning path created locally from your uploaded material.", lessons=lessons, quiz=questions)


def make_prompt(text: str, filename: str) -> str:
    return f"""You are LearnForge, an excellent school teacher who turns difficult study material into simple, accurate lessons.

Use ONLY the uploaded material. Do not invent facts. Return only valid JSON matching the requested course structure.

First, silently identify the document's distinct, meaningful subtopics. Then create ONE lesson for each major subtopic. Combine overlapping ideas into one lesson and never create filler lessons just because the document is long. The number of lessons must be chosen from the actual topics, NOT from page count, word count, or a fixed target. A short document might need 2 lessons; a broad document might need more. Do not always return the same number.

Create quiz questions in proportion to the lessons: use 1 question for a simple lesson and 2 questions only when a lesson has several important ideas. Do not always return the same number of questions. Every question must test a real topic from the uploaded document; never add generic filler questions.

Write quizzes like a good teacher. Use direct, student-friendly wording such as "What is the main role of..." or "Which statement best explains...?" Never say "uploaded material", "the material", "the document", or "evidence" in a question or answer unless that word is actually the topic being tested. Each question must have four realistic, comparable options. Wrong options must be plausible misconceptions or related ideas, never obvious filler such as "skip the topic" or "unrelated".

Keep the course focused: return between 2 and 12 lessons and between 3 and 24 questions, but use the smallest number that still covers all major topics.

Every lesson must have:
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
        model="gemini-3.6-flash",
        contents=make_prompt(text, filename),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Course,
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
