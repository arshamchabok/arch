from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import SQLModel, create_engine, Session, select
from models import Code, gen_code
from typing import List
from dotenv import load_dotenv
import os, json, shutil, smtplib
from email.message import EmailMessage
from email.utils import formatdate

load_dotenv()

# ---------- Questions (labels used in the email) ----------
QUESTIONS = [
  # 1. Personal Background & Daily Life
  "What does a typical weekday look like for you from morning to night?",
  "How do you usually spend your weekends?",
  "How many hours a day do you spend at home versus outside?",
  "Do you prefer a quiet, calm environment or a lively, energetic atmosphere?",
  "Who do you usually spend most of your time with at home (alone, family, friends, pets)?",
  # 2. Emotional & Sensory Preferences
  "Which three places in the world have made you feel happiest or most inspired?",
  "Which three places have made you feel uncomfortable or unhappy?",
  "What smells instantly make you feel relaxed?",
  "What sounds do you find calming, and which do you dislike?",
  "Do you enjoy the sight and smell of plants, flowers, and greenery around you?",
  # 3. Visual Style & Color
  "What are your top three favorite colors?",
  "Are there any colors you absolutely dislike or avoid?",
  "Do you prefer light, airy spaces or dark, cozy ones?",
  "When you imagine your dream home, is it modern, classic, rustic, bohemian, or something else?",
  "Do you like symmetry and clean lines, or do you enjoy organic and irregular shapes?",
  # 4. Functional Lifestyle Needs
  "Which room in your home do you use the most, and why?",
  "Which room in your current home do you feel is “missing” or could be better designed?",
  "How often do you cook at home?",
  "Do you host guests often? If yes, what kind of gatherings?",
  "Would you like to have a garden, terrace plants, or indoor greenery as part of your home?",
  # 5. Hobbies & Leisure
  "What are your main hobbies or activities in your free time?",
  "Do you prefer indoor or outdoor activities?",
  "If you could add one leisure space to your home (library, art studio, home theater, garden, gym), what would it be?",
  "Do you collect anything or have items that need special display or storage?",
  "When traveling, do you choose destinations with a lot of natural scenery, parks, or green spaces?",
  # 6. Personality & Social Preferences
  "Do you feel more energized by socializing or by spending time alone?",
  "Are you more spontaneous or more of a planner?",
  "Do you enjoy bold, statement-making spaces or subtle, timeless designs?",
  "Do you feel more inspired in nature-rich environments or in urban/city settings?",
  # 7. Future Aspirations
  "If money and space were no limit, what would your ideal home look and feel like — and how much of it would be surrounded by greenery or nature?"
]

# ---------- Email config ----------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "no-reply@example.com")
print("SMTP DEBUG -> HOST:", SMTP_HOST, "PORT:", SMTP_PORT, "USER:", SMTP_USER, "FROM:", FROM_EMAIL)

# ---------- App / DB ----------
FOUNDER_KEY = os.environ.get("FOUNDER_KEY", "letmein")
DB_URL = "sqlite:///app.db"

app = FastAPI(title="Studio Intake")
app.mount("/static", StaticFiles(directory="static"), name="static")
engine = create_engine(DB_URL, echo=False)
templates = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)

@app.on_event("startup")
def startup():
    # ensure uploads dir exists
    os.makedirs("static/uploads", exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

@app.get("/")
def home():
    return {"message": "✅ Server is running"}

def require_founder(request: Request):
    if request.query_params.get("key") != FOUNDER_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True

# ---------- Founder admin ----------
@app.get("/founder", response_class=HTMLResponse)
def founder_page(request: Request, ok: int | None = None, _: bool = Depends(require_founder), session: Session = Depends(get_session)):
    codes = session.exec(select(Code).order_by(Code.id.desc())).all()
    tpl = templates.get_template("founder.html")
    return tpl.render(request=request, codes=codes, ok=ok, key=request.query_params.get("key"))

@app.post("/founder/create")
def founder_create(request: Request, architect_email: str = Form(...), _: bool = Depends(require_founder), session: Session = Depends(get_session)):
    c = Code(code=gen_code(), architect_email=architect_email)
    session.add(c); session.commit()
    key = request.query_params.get("key")
    return RedirectResponse(url=f"/founder?key={key}&ok=1", status_code=303)

@app.post("/founder/toggle/{code}")
def founder_toggle(code: str, request: Request, _: bool = Depends(require_founder), session: Session = Depends(get_session)):
    obj = session.exec(select(Code).where(Code.code == code)).first()
    if not obj: raise HTTPException(404, "Code not found")
    obj.is_active = not obj.is_active
    session.add(obj); session.commit()
    key = request.query_params.get("key")
    return RedirectResponse(url=f"/founder?key={key}", status_code=303)

# ---------- Client start ----------
@app.get("/start", response_class=HTMLResponse)
def client_start_page(request: Request):
    tpl = templates.get_template("client_start.html")
    return tpl.render(request=request, error=None)

@app.post("/start", response_class=HTMLResponse)
def client_start_submit(
    request: Request,
    code: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    dob: str = Form(...),
    session: Session = Depends(get_session),
):
    from models import Submission
    # validate code
    c = session.exec(select(Code).where(Code.code == code, Code.is_active == True)).first()
    if not c:
        tpl = templates.get_template("client_start.html")
        return tpl.render(request=request, error="Invalid or inactive code.")

    # save submission
    sub = Submission(
        code=code,
        client_first_name=first_name.strip(),
        client_last_name=last_name.strip(),
        client_email=email.strip(),
        client_dob=datetime.strptime(dob, "%Y-%m-%d").date(),
        status="DRAFT",
    )
    session.add(sub); session.commit(); session.refresh(sub)

    return RedirectResponse(url=f"/client/{sub.id}/survey", status_code=303)

# ---------- Survey (answers + photos) ----------
@app.get("/client/{sub_id}/survey", response_class=HTMLResponse)
def survey_page(sub_id: int, request: Request, session: Session = Depends(get_session)):
    from models import Submission, Photo
    sub = session.get(Submission, sub_id)
    if not sub:
        raise HTTPException(404, "Submission not found")

    answers = {}
    if getattr(sub, "answers_json", None):
        try:
            answers = json.loads(sub.answers_json)
        except Exception:
            answers = {}

    photos = session.exec(select(Photo).where(Photo.submission_id == sub_id).order_by(Photo.id.desc())).all()

    tpl = templates.get_template("survey.html")
    return tpl.render(request=request, sub=sub, answers=answers, photos=photos)

@app.post("/client/{sub_id}/survey", response_class=HTMLResponse)
async def survey_submit(sub_id: int, request: Request, session: Session = Depends(get_session)):
    from models import Submission
    sub = session.get(Submission, sub_id)
    if not sub:
        raise HTTPException(404, "Submission not found")

    try:
        form = await request.form()
        answers = {f"q{i}": (form.get(f"q{i}") or "").strip() for i in range(1, 31)}
        sub.answers_json = json.dumps(answers, ensure_ascii=False)
        sub.status = "SUBMITTED"
        session.add(sub)
        session.commit()

        # try to email (don’t break user flow if it fails)
        try:
            send_submission_email(sub.id, session)
        except Exception:
            pass

        tpl = templates.get_template("survey_thanks.html")
        return tpl.render(request=request, sub=sub)
    except Exception as e:
        return HTMLResponse(f"<pre>ERROR: {type(e).__name__}: {e}</pre>", status_code=500)

@app.post("/client/{sub_id}/upload", response_class=HTMLResponse)
async def upload_photos(
    sub_id: int,
    request: Request,
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    from models import Submission, Photo
    sub = session.get(Submission, sub_id)
    if not sub:
        raise HTTPException(404, "Submission not found")

    current = session.exec(select(Photo).where(Photo.submission_id == sub_id)).all()
    remaining = 10 - len(current)
    if remaining <= 0:
        return RedirectResponse(url=f"/client/{sub_id}/survey", status_code=303)

    saved = False
    for f in files[:remaining]:
        if f.content_type not in ("image/jpeg", "image/png", "image/webp"):
            continue

        ext = ""
        if "." in (f.filename or ""):
            ext = "." + f.filename.rsplit(".", 1)[1].lower()
        unique_name = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        rel_path = f"static/uploads/{unique_name}{ext}"
        abs_path = os.path.join(os.getcwd(), rel_path.replace("/", os.sep))

        with open(abs_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)

        photo = Photo(
            submission_id=sub_id,
            file_path=rel_path,
            original_name=f.filename or "",
            content_type=f.content_type or "",
        )
        session.add(photo)
        saved = True

    if saved:
        session.commit()

    return RedirectResponse(url=f"/client/{sub_id}/survey", status_code=303)

@app.post("/client/{sub_id}/photo/{photo_id}/delete")
def delete_photo(sub_id: int, photo_id: int, session: Session = Depends(get_session)):
    from models import Photo
    photo = session.get(Photo, photo_id)
    if not photo or photo.submission_id != sub_id:
        raise HTTPException(404, "Photo not found")

    try:
        p = os.path.join(os.getcwd(), photo.file_path.replace("/", os.sep))
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass

    session.delete(photo)
    session.commit()
    return RedirectResponse(url=f"/client/{sub_id}/survey", status_code=303)

# ---------- Email helper ----------
def send_submission_email(submission_id: int, session: Session):
    from models import Submission, Photo, Code
    sub = session.get(Submission, submission_id)
    if not sub:
        return

    code_row = session.exec(select(Code).where(Code.code == sub.code)).first()
    if not code_row:
        return
    to_email = code_row.architect_email

    answers = {}
    if getattr(sub, "answers_json", None):
        try:
            answers = json.loads(sub.answers_json)
        except Exception:
            answers = {}

    lines = []
    lines.append(f"<h2>New Client Submission (#{sub.id})</h2>")
    lines.append(f"<p><b>Code:</b> {sub.code}</p>")
    lines.append(f"<p><b>Client:</b> {sub.client_first_name} {sub.client_last_name} — {sub.client_email}</p>")
    lines.append("<hr>")
    lines.append("<h3>Answers</h3>")
    lines.append("<ol>")
    # Use full question text instead of Q1/Q2 labels
    for i in range(1, 31):
        q_text = QUESTIONS[i-1] if i-1 < len(QUESTIONS) else f"Question {i}"
        val = (answers.get(f"q{i}", "") or "").replace('\n', '<br>')
        lines.append(f"<li><div style='margin-bottom:10px'><b>{q_text}</b><br>{val}</div></li>")
    lines.append("</ol>")

    photos = session.exec(select(Photo).where(Photo.submission_id == sub.id)).all()
    if photos:
        lines.append("<h3>Photos</h3><ul>")
        for p in photos:
            lines.append(f"<li>{p.original_name} <small>({p.content_type})</small></li>")
        lines.append("</ul>")

    html = "\n".join(lines)

    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and FROM_EMAIL and to_email):
        return  # email not configured

    msg = EmailMessage()
    msg['Subject'] = f"Client Intake #{sub.id} — Code {sub.code}"
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Date'] = formatdate(localtime=True)
    msg.set_content("Your email client does not support HTML.")
    msg.add_alternative(html, subtype='html')

    # Attach photos (watch total size with Gmail)
    for p in photos:
        try:
            path = os.path.join(os.getcwd(), p.file_path.replace("/", os.sep))
            with open(path, "rb") as fp:
                data = fp.read()
            maintype, subtype = (p.content_type.split("/", 1) + ["octet-stream"])[:2]
            msg.add_attachment(data, maintype=maintype, subtype=subtype,
                               filename=p.original_name or os.path.basename(path))
        except Exception:
            continue

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
