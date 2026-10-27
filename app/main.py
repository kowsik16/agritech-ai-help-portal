import os, time, logging, re
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Text, DateTime, Integer, Boolean, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agritech")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agritech.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine_args = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class FAQ(Base):
    __tablename__ = "faqs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(300), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="General")

class Ticket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Website visitor")
    email: Mapped[str] = mapped_column(String(254), default="")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ErrorCode(Base):
    __tablename__ = "error_codes"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)

SEED_FAQS = [
("What is precision weeding?", "Precision weeding identifies weeds and removes or targets them while minimizing damage to nearby crops.", "Precision Farming"),
("How does computer vision help farmers?", "Computer vision analyzes camera images to identify crops, weeds, and field conditions. Results depend on lighting, camera angle, and training data.", "AI & Vision"),
("What is the difference between a crop and a weed?", "A crop is the plant being cultivated; a weed is an unwanted plant competing for resources. Identification should be verified before physical removal.", "Crop Care"),
("What is an AI crop detection model?", "It is a trained machine-learning model that predicts object classes and locations in images, often using bounding boxes and confidence scores.", "AI & Vision"),
("What does a confidence score mean?", "A confidence score estimates how strongly a model supports a prediction. It is not a guarantee of correctness; validate it with field data.", "AI & Vision"),
("Why can a model miss a weed?", "Poor lighting, occlusion, unfamiliar growth stages, motion blur, and limited or imbalanced training examples can reduce detection performance.", "Troubleshooting"),
("How should I collect field images?", "Collect varied images across lighting, soil, crop stages, distances, and weed types. Label consistently and keep separate training, validation, and test sets.", "Data Collection"),
("Can the system damage crops?", "Yes, a mistaken detection or actuator error can damage crops. Start with a detection-only demo, use a safe test area, and add a human-confirmation and emergency-stop process before actuation.", "Safety"),
("What is a dataset annotation?", "Annotation adds labels and, for object detection, bounding boxes around each target so the model can learn where objects appear.", "AI & Vision"),
("How can I improve detection accuracy?", "Review false positives and missed detections, collect representative field samples, improve labels, train and validate again, and evaluate on a held-out field test set.", "Model Improvement"),
("Does the portal need internet access?", "The basic FAQ and error-code pages can work from the application database. The weather feature and hosted AI provider require network access; fallback answers are provided when unavailable.", "Website Help"),
("How do I report an issue?", "Use the assistant to describe the issue. If it cannot answer confidently, choose Create support ticket and submit the question with optional contact details.", "Support"),
]
SEED_ERRORS = [
(400, "Bad Request", "The server could not process the request because its input is invalid.", "Check required fields, data types, and request format before retrying."),
(401, "Unauthorized", "Authentication is missing or invalid.", "Sign in again and verify that credentials or tokens are valid."),
(403, "Forbidden", "The server understood the request but access is not allowed.", "Check account permissions. Signing in again may not grant the required access."),
(404, "Not Found", "The requested page or resource does not exist.", "Check the URL or return to the home page. Ask the assistant for help."),
(429, "Too Many Requests", "Too many requests were sent in a short period.", "Wait, respect any Retry-After guidance, and reduce repeated requests."),
(500, "Internal Server Error", "The server encountered an unexpected condition.", "Retry once later. If it continues, report the issue using the assistant or support ticket."),
(503, "Service Unavailable", "The service is temporarily unavailable or overloaded.", "Wait briefly and retry. Check the service health endpoint."),
(460, "Crop Data Validation Error (site-specific)", "AgriTech Portal custom code: submitted crop or field data did not pass the portal's validation rules. This is not a standard HTTP status code.", "Check that required crop fields are present and values use the expected format, then submit again."),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(FAQ.id).limit(1)) is None:
            db.add_all([FAQ(question=q, answer=a, category=c) for q,a,c in SEED_FAQS])
        if db.scalar(select(ErrorCode.code).limit(1)) is None:
            db.add_all([ErrorCode(code=c, title=t, explanation=e, solution=s) for c,t,e,s in SEED_ERRORS])
        db.commit()
    yield

app = FastAPI(title="AgriTech AI Help Portal", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Mongo is optional during local development. The app remains usable if Mongo is unavailable.
mongo_collection = None
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if mongo_uri:
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
        mongo_client.admin.command("ping")
        mongo_collection = mongo_client[os.getenv("MONGODB_DATABASE", "agritech_portal")]["events"]
except Exception as exc:
    logger.warning("MongoDB unavailable; chat/feedback persistence disabled: %s", exc)

@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error path=%s", request.url.path)
        response = JSONResponse({"detail": "Unexpected server error. Please try again or ask the assistant.", "code": 500}, status_code=500)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info("method=%s path=%s status=%s duration_ms=%s", request.method, request.url.path, response.status_code, duration_ms)
    response.headers["X-Process-Time-ms"] = str(duration_ms)
    return response

def log_mongo(kind: str, payload: dict):
    if mongo_collection is not None:
        try:
            mongo_collection.insert_one({"kind": kind, "created_at": datetime.now(timezone.utc), **payload})
        except PyMongoError as exc:
            logger.warning("Could not save Mongo event: %s", exc)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"page": "home"})

@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse(request=request, name="faq.html", context={"page": "faq"})

@app.get("/errors", response_class=HTMLResponse)
async def errors_page(request: Request):
    return templates.TemplateResponse(request=request, name="errors.html", context={"page": "errors"})

@app.get("/404", response_class=HTMLResponse)
async def custom_404(request: Request):
    return templates.TemplateResponse(request=request, name="404.html", context={"page": "404"}, status_code=404)

@app.get("/500", response_class=HTMLResponse)
async def custom_500(request: Request):
    return templates.TemplateResponse(request=request, name="500.html", context={"page": "500"}, status_code=500)

@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "API endpoint not found", "code": 404}, status_code=404)
    return templates.TemplateResponse(request=request, name="404.html", context={"page": "404"}, status_code=404)

@app.exception_handler(500)
async def server_error(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Unexpected server error", "code": 500}, status_code=500)
    return templates.TemplateResponse(request=request, name="500.html", context={"page": "500"}, status_code=500)

@app.get("/api/faqs")
def get_faqs():
    with SessionLocal() as db:
        rows = db.scalars(select(FAQ).order_by(FAQ.id)).all()
        return [{"id":r.id,"question":r.question,"answer":r.answer,"category":r.category} for r in rows]

@app.get("/api/errors")
def get_errors():
    with SessionLocal() as db:
        rows = db.scalars(select(ErrorCode).order_by(ErrorCode.code)).all()
        return [{"code":r.code,"title":r.title,"explanation":r.explanation,"solution":r.solution} for r in rows]

@app.get("/api/health")
def health():
    sql_status = "ok"
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:
        sql_status = "error"
    mongo_status = "ok" if mongo_collection is not None else "not_configured_or_unavailable"
    status = "ok" if sql_status == "ok" else "degraded"
    return JSONResponse({"status": status, "service": "agritech-ai-help-portal", "sql": sql_status, "mongodb": mongo_status, "timestamp": datetime.now(timezone.utc).isoformat()}, status_code=200 if status=="ok" else 503)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="anonymous", max_length=120)

class TicketRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    name: str = Field(default="Website visitor", max_length=120)
    email: str = Field(default="", max_length=254)

class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)
    session_id: str = Field(default="anonymous", max_length=120)

def find_faq_answer(message: str):
    words = set(re.findall(r"[a-z0-9]+", message.lower()))
    stop = {"what","how","does","can","the","is","a","an","i","my","it","to","for","of","in","on","do","why","with","and"}
    words -= stop
    with SessionLocal() as db:
        rows = db.scalars(select(FAQ)).all()
    best, best_score = None, 0
    for row in rows:
        haystack = set(re.findall(r"[a-z0-9]+", (row.question + " " + row.answer + " " + row.category).lower())) - stop
        score = len(words & haystack) / max(1, len(words))
        if score > best_score:
            best, best_score = row, score
    return (best, best_score)

def error_answer(message: str):
    match = re.search(r"\b(400|401|403|404|429|500|503|460)\b", message)
    if not match: return None
    code = int(match.group(1))
    with SessionLocal() as db:
        row = db.get(ErrorCode, code)
    if not row: return None
    return f"**{row.code} — {row.title}**\n\n{row.explanation}\n\n**What to try:** {row.solution}"

async def ask_llm(message: str, faq_context: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                      "messages":[
                        {"role":"system","content":"You are the AgriTech AI Help Portal assistant. Answer only from the FAQ context below and general safe troubleshooting. If context is insufficient, say you cannot confidently answer and suggest creating a support ticket. Do not claim to control farm machinery. For agricultural safety, recommend testing in a safe area and human verification.\nFAQ context:\n"+faq_context},
                        {"role":"user","content":message}],
                      "temperature":0.2})
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("AI provider timeout/failure; using retrieval fallback: %s", exc)
        return None

@app.post("/api/chat")
async def chat(body: ChatRequest):
    message = body.message.strip()
    err = error_answer(message)
    if err:
        answer, confident = err, True
    else:
        faq, score = find_faq_answer(message)
        context = f"Q: {faq.question}\nA: {faq.answer}" if faq and score >= 0.25 else ""
        llm_answer = await ask_llm(message, context)
        if llm_answer:
            answer, confident = llm_answer, True
        elif faq and score >= 0.25:
            answer, confident = faq.answer, True
        else:
            answer, confident = ("I couldn't find a reliable answer in the current AgriTech FAQ. You can create a support ticket and the team can follow up. Please include the crop, device, error message, and steps you already tried.", False)
    log_mongo("chat", {"session_id": body.session_id, "question": message, "answer": answer, "confident": confident})
    return {"answer": answer, "confident": confident, "offer_ticket": not confident}

@app.post("/api/tickets", status_code=201)
def create_ticket(body: TicketRequest):
    with SessionLocal() as db:
        ticket = Ticket(name=body.name.strip() or "Website visitor", email=body.email.strip(), question=body.question.strip())
        db.add(ticket); db.commit(); db.refresh(ticket)
        ticket_id = ticket.id
    log_mongo("ticket_created", {"ticket_id": ticket_id, "email_provided": bool(body.email.strip())})
    return {"ticket_id": ticket_id, "status": "OPEN", "message": "Support ticket created successfully."}

@app.post("/api/feedback", status_code=201)
def feedback(body: FeedbackRequest):
    log_mongo("feedback", {"rating": body.rating, "comment": body.comment.strip(), "session_id": body.session_id})
    # A successful response also lets local demos work before Mongo is configured.
    return {"saved": mongo_collection is not None, "message": "Feedback received." if mongo_collection is not None else "Feedback received; configure MONGODB_URI to persist it in MongoDB."}

@app.get("/api/weather")
async def weather(city: str = "Coimbatore"):
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        return {"source":"fallback","city":city,"summary":"Weather service is not configured. Demonstration fallback: check your local forecast before field work.","temperature_c":None}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
            resp = await client.get("https://api.openweathermap.org/data/2.5/weather", params={"q":city,"appid":key,"units":"metric"})
            resp.raise_for_status()
            data = resp.json()
            return {"source":"openweather","city":data.get("name",city),"summary":data["weather"][0]["description"],"temperature_c":data["main"]["temp"]}
    except Exception as exc:
        logger.warning("Weather API unavailable; returning fallback: %s", exc)
        return {"source":"fallback","city":city,"summary":"Live weather is temporarily unavailable. Check an official local forecast before spraying, weeding, or operating machinery.","temperature_c":None}
