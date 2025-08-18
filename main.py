from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import SQLModel, create_engine, Session, select
from models import Code, gen_code
import os
#to start again
#& "C:/Users/ARSHAM CHABOK/Desktop/arch/venv/Scripts/Activate.ps1"
#pip install -r requirements.txt
#python -m uvicorn app:app --reload --port 8001 


# restart:python -m uvicorn app:app --reload --port 8001

#start your sever1: .\venv\Scripts\activate
#start your sever2: python -m uvicorn app:app --reload --port 8001 


# ---- Config (change this later) ----
FOUNDER_KEY = os.environ.get("FOUNDER_KEY", "letmein")  # URL key: ?key=letmein
DB_URL = "sqlite:///app.db"

# ---- App & DB ----
app = FastAPI(title="Studio Intake")
engine = create_engine(DB_URL, echo=False)
templates = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)

@app.on_event("startup")
def startup():
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
# ---- Client: start page (enter code + personal info) ----
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
    # validate code is active
    c = session.exec(select(Code).where(Code.code == code, Code.is_active == True)).first()
    if not c:
        tpl = templates.get_template("client_start.html")
        return tpl.render(request=request, error="Invalid or inactive code.")

    # create submission
    from models import Submission
    sub = Submission(
        code=code,
        client_first_name=first_name.strip(),
        client_last_name=last_name.strip(),
        client_email=email.strip(),
        client_dob=datetime.strptime(dob, "%Y-%m-%d").date(),
        status="DRAFT",
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    # go to survey placeholder (we'll add questions next)
    return RedirectResponse(url=f"/client/{sub.id}/survey", status_code=303)

@app.get("/client/{sub_id}/survey", response_class=HTMLResponse)
def survey_placeholder(sub_id: int, request: Request, session: Session = Depends(get_session)):
    from models import Submission
    sub = session.get(Submission, sub_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    tpl = templates.get_template("survey_placeholder.html")
    return tpl.render(request=request, sub=sub)

