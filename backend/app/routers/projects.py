from datetime import datetime, time
import os
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, ProjectSubmission, ProjectSubmissionStatus, User
from app.routers.users import get_current_active_member, get_current_admin_user
from app.schemas import AdminProjectSubmissionOut, ProjectNotesUpdate, ProjectSubmissionOut


router = APIRouter(tags=["Projects"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_UPLOADS_DIR = BACKEND_DIR / "uploads" / "projects"
PROJECT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MAX_PROJECT_FILE_SIZE = 25 * 1024 * 1024


def _status_to_api(status: str | ProjectSubmissionStatus) -> str:
    if isinstance(status, ProjectSubmissionStatus):
        return status.value
    if not status:
        return ProjectSubmissionStatus.PENDING.value
    normalized = str(status).lower()
    if normalized in {item.value for item in ProjectSubmissionStatus}:
        return normalized
    try:
        return ProjectSubmissionStatus[str(status)].value
    except KeyError:
        return normalized


def _status_to_db(status: ProjectSubmissionStatus) -> str:
    return status.name


def _uploaded_project_path(file_url: str | None) -> Path | None:
    if not file_url:
        return None
    prefix = "/uploads/projects/"
    if not file_url.startswith(prefix):
        return None
    candidate = (PROJECT_UPLOADS_DIR / file_url.removeprefix(prefix)).resolve()
    uploads_root = PROJECT_UPLOADS_DIR.resolve()
    if uploads_root not in candidate.parents and candidate != uploads_root:
        return None
    return candidate


def _serialize_submission(submission: ProjectSubmission) -> dict:
    return {
        "id": submission.id,
        "user_id": submission.user_id,
        "course_id": submission.course_id,
        "file_name": submission.file_name,
        "file_url": submission.file_url,
        "json_payload": submission.json_payload,
        "status": _status_to_api(submission.status),
        "admin_notes": submission.admin_notes,
        "reviewed_by": submission.reviewed_by,
        "reviewed_at": submission.reviewed_at,
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
    }


def _serialize_admin_submission(submission: ProjectSubmission) -> dict:
    data = _serialize_submission(submission)
    data.update({
        "member_name": submission.user.full_name if submission.user else "Unknown member",
        "member_email": submission.user.email if submission.user else "",
        "course_title": submission.course.title if submission.course else "Unknown course",
        "reviewer_name": submission.reviewer.full_name if submission.reviewer else None,
    })
    return data


def _parse_date_boundary(value: str | None, is_end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed_date = datetime.fromisoformat(value).date()
            return datetime.combine(parsed_date, time.max if is_end else time.min)
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date filter")


async def _read_and_validate_project_file(file: UploadFile) -> tuple[bytes, dict]:
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Project file cannot be empty")
    if len(raw) > MAX_PROJECT_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Project file must be 25MB or smaller")

    original_name = file.filename or ""
    if not original_name:
        raise HTTPException(status_code=400, detail="Project file must have a name")

    payload = {
        "kind": "uploaded_file",
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": len(raw),
        "original_name": os.path.basename(original_name),
    }

    return raw, payload


@router.post("/projects/submit", response_model=ProjectSubmissionOut, status_code=201)
async def submit_project(
    course_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id, Course.is_published == True).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    raw, payload = await _read_and_validate_project_file(file)

    original_name = os.path.basename(file.filename or "project.json")
    safe_original = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in original_name)
    unique_name = f"user_{current_user.id}_course_{course_id}_{uuid.uuid4().hex[:12]}_{safe_original}"
    file_path = PROJECT_UPLOADS_DIR / unique_name
    with open(file_path, "wb") as out_file:
        out_file.write(raw)

    submission = ProjectSubmission(
        user_id=current_user.id,
        course_id=course_id,
        file_name=original_name,
        file_url=f"/uploads/projects/{unique_name}",
        json_payload=payload,
        status=_status_to_db(ProjectSubmissionStatus.PENDING),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return _serialize_submission(submission)


@router.get("/projects/my-projects", response_model=list[ProjectSubmissionOut])
def my_projects(
    course_id: int | None = Query(None),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    query = db.query(ProjectSubmission).filter(ProjectSubmission.user_id == current_user.id)
    if course_id:
        query = query.filter(ProjectSubmission.course_id == course_id)
    submissions = query.order_by(ProjectSubmission.created_at.desc()).all()
    return [_serialize_submission(submission) for submission in submissions]


@router.get("/projects/{project_id}", response_model=ProjectSubmissionOut)
def get_my_project(
    project_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    submission = db.query(ProjectSubmission).filter(
        ProjectSubmission.id == project_id,
        ProjectSubmission.user_id == current_user.id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")
    return _serialize_submission(submission)


@router.get("/admin/projects", response_model=list[AdminProjectSubmissionOut])
def admin_projects(
    status: str | None = Query(None),
    course_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(ProjectSubmission).join(User, ProjectSubmission.user_id == User.id).join(Course, ProjectSubmission.course_id == Course.id)

    if status and status != "all":
        allowed = {item.value for item in ProjectSubmissionStatus}
        if status not in allowed:
            raise HTTPException(status_code=400, detail="Invalid project status")
        status_value = ProjectSubmissionStatus(status)
        query = query.filter(cast(ProjectSubmission.status, String).in_([status_value.value, status_value.name]))
    if course_id:
        query = query.filter(ProjectSubmission.course_id == course_id)

    start_at = _parse_date_boundary(date_from)
    end_at = _parse_date_boundary(date_to, is_end=True)
    if start_at:
        query = query.filter(ProjectSubmission.created_at >= start_at)
    if end_at:
        query = query.filter(ProjectSubmission.created_at <= end_at)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            User.full_name.ilike(term),
            User.email.ilike(term),
            Course.title.ilike(term),
            ProjectSubmission.file_name.ilike(term),
        ))

    submissions = query.order_by(ProjectSubmission.created_at.desc()).all()
    return [_serialize_admin_submission(submission) for submission in submissions]


@router.get("/admin/projects/{project_id}", response_model=AdminProjectSubmissionOut)
def admin_project_detail(
    project_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")
    return _serialize_admin_submission(submission)


@router.get("/admin/projects/{project_id}/download")
def download_project_file(
    project_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Stream a member's submitted project file to the admin as a download (admin only)."""
    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")

    file_path = _uploaded_project_path(submission.file_url)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Project file not found on server")

    download_name = submission.file_name or file_path.name
    media_type = "application/octet-stream"
    if isinstance(submission.json_payload, dict):
        media_type = submission.json_payload.get("content_type") or media_type

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type=media_type,
    )


@router.post("/admin/projects/{project_id}/approve", response_model=AdminProjectSubmissionOut)
def approve_project(
    project_id: int,
    notes: ProjectNotesUpdate | None = None,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")

    submission.status = _status_to_db(ProjectSubmissionStatus.APPROVED)
    if notes and notes.notes.strip():
        submission.admin_notes = notes.notes.strip()
    submission.reviewed_by = admin.id
    submission.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(submission)
    return _serialize_admin_submission(submission)


@router.post("/admin/projects/{project_id}/request-changes", response_model=AdminProjectSubmissionOut)
def request_project_changes(
    project_id: int,
    notes: ProjectNotesUpdate,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    if not notes.notes.strip():
        raise HTTPException(status_code=400, detail="Review notes are required when requesting changes")

    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")

    submission.status = _status_to_db(ProjectSubmissionStatus.CHANGES_REQUESTED)
    submission.admin_notes = notes.notes.strip()
    submission.reviewed_by = admin.id
    submission.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(submission)
    return _serialize_admin_submission(submission)


@router.post("/admin/projects/{project_id}/notes", response_model=AdminProjectSubmissionOut)
def update_project_notes(
    project_id: int,
    notes: ProjectNotesUpdate,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")

    submission.admin_notes = notes.notes.strip() or None
    submission.reviewed_by = admin.id
    submission.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(submission)
    return _serialize_admin_submission(submission)


@router.delete("/admin/projects/{project_id}", status_code=204)
def delete_project_submission(
    project_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    submission = db.query(ProjectSubmission).filter(ProjectSubmission.id == project_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Project submission not found")

    file_path = _uploaded_project_path(submission.file_url)
    db.delete(submission)
    db.commit()

    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    return None
