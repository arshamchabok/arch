from typing import Optional
from datetime import datetime, date
import uuid
from sqlmodel import SQLModel, Field

def gen_code() -> str:
    # 8-char code like A9K2Q7XZ
    return uuid.uuid4().hex[:8].upper()

class Code(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    architect_email: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Submission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)          # the 8-char client code
    client_first_name: str
    client_last_name: str
    client_email: str
    client_dob: date
    status: str = "DRAFT"                  # DRAFT -> SUBMITTED
    answers_json: Optional[str] = None     # stores all 30 answers as JSON text
    created_at: datetime = Field(default_factory=datetime.utcnow)
class Photo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: int = Field(index=True)
    file_path: str                               # e.g., "static/uploads/abcd1234.jpg"
    original_name: str                           # original filename from user
    content_type: str                            # image/jpeg, image/png, image/webp
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
