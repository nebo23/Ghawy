from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Exam, ExamAttempt, Lesson, User
from app.routers.users import (
    get_current_active_member,
    get_current_user,
    get_current_owner_user,
)
from app.schemas import ExamCreate, ExamSubmit, ExamUpdate


router = APIRouter(tags=["Exams"])


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _normalize_questions(raw_questions) -> list[dict]:
    """Validate + normalize the incoming questions payload into a clean list."""
    normalized = []
    for q in raw_questions or []:
        # q may be a pydantic model (ExamQuestionIn) or a dict
        text = (getattr(q, "text", None) if not isinstance(q, dict) else q.get("text")) or ""
        options = (getattr(q, "options", None) if not isinstance(q, dict) else q.get("options")) or []
        correct = (getattr(q, "correct", None) if not isinstance(q, dict) else q.get("correct"))

        text = str(text).strip()
        clean_options = [str(o).strip() for o in options if str(o).strip() != ""]
        if not text or len(clean_options) < 2:
            # skip incomplete questions (need a prompt + at least 2 options)
            continue
        try:
            correct = int(correct)
        except (TypeError, ValueError):
            correct = 0
        if correct < 0 or correct >= len(clean_options):
            correct = 0
        normalized.append({"text": text, "options": clean_options, "correct": correct})
    return normalized


def _validate_after_lesson(db: Session, course_id: int, after_lesson_id) -> int | None:
    """Ensure the placement lesson exists and belongs to the same course."""
    if after_lesson_id is None:
        return None
    lesson = (
        db.query(Lesson)
        .filter(Lesson.id == after_lesson_id, Lesson.course_id == course_id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=400, detail="after_lesson_id does not belong to this course")
    return lesson.id


def _serialize_admin_exam(exam: Exam) -> dict:
    """Full exam incl. correct answers — admin/team only."""
    return {
        "id": exam.id,
        "course_id": exam.course_id,
        "title": exam.title,
        "description": exam.description,
        "pass_percent": exam.pass_percent,
        "questions": exam.questions or [],
        "question_count": len(exam.questions or []),
        "is_published": exam.is_published,
        "sort_order": exam.sort_order,
        "after_lesson_id": exam.after_lesson_id,
        "created_at": exam.created_at,
    }


def _public_question(q: dict) -> dict:
    """Strip the correct answer before sending questions to a member."""
    return {"text": q.get("text", ""), "options": q.get("options", [])}


def _best_attempt(db: Session, exam_id: int, user_id: int) -> ExamAttempt | None:
    return (
        db.query(ExamAttempt)
        .filter(ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user_id)
        .order_by(ExamAttempt.score.desc(), ExamAttempt.created_at.desc())
        .first()
    )


def _serialize_member_exam_summary(db: Session, exam: Exam, user_id: int) -> dict:
    best = _best_attempt(db, exam.id, user_id)
    attempts_count = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.exam_id == exam.id, ExamAttempt.user_id == user_id)
        .count()
    )
    return {
        "id": exam.id,
        "course_id": exam.course_id,
        "title": exam.title,
        "description": exam.description,
        "pass_percent": exam.pass_percent,
        "question_count": len(exam.questions or []),
        "sort_order": exam.sort_order,
        "after_lesson_id": exam.after_lesson_id,
        "attempts_count": attempts_count,
        "best_score": best.score if best else None,
        "passed": bool(best.passed) if best else False,
    }


# ═══════════════════════════════════════════════════════════════
#  MEMBER ENDPOINTS
# ═══════════════════════════════════════════════════════════════
# All three take get_current_active_member. Listing and fetching used to take
# get_current_user, so a free registered account could pull every published
# exam's questions — submit_exam was the only one that asked whether the caller
# was actually paying.

@router.get("/courses/{course_id}/exams")
def list_course_exams(
    course_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """List published exams for a course with this member's progress on each."""
    exams = (
        db.query(Exam)
        .filter(Exam.course_id == course_id, Exam.is_published == True)
        .order_by(Exam.sort_order.asc(), Exam.id.asc())
        .all()
    )
    return [_serialize_member_exam_summary(db, exam, current_user.id) for exam in exams]


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Fetch a published exam's questions (WITHOUT correct answers) so a member can take it."""
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_published == True).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    best = _best_attempt(db, exam.id, current_user.id)
    return {
        "id": exam.id,
        "course_id": exam.course_id,
        "title": exam.title,
        "description": exam.description,
        "pass_percent": exam.pass_percent,
        "questions": [_public_question(q) for q in (exam.questions or [])],
        "best_score": best.score if best else None,
        "passed": bool(best.passed) if best else False,
    }


@router.post("/exams/{exam_id}/submit")
def submit_exam(
    exam_id: int,
    payload: ExamSubmit,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Grade a member's answers, store the attempt, and return the result with correct answers."""
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_published == True).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = exam.questions or []
    total = len(questions)
    if total == 0:
        raise HTTPException(status_code=400, detail="This exam has no questions yet")

    answers = payload.answers or {}
    results = []
    correct_count = 0
    for idx, q in enumerate(questions):
        selected = answers.get(str(idx))
        if selected is None:
            selected = answers.get(idx)  # tolerate int keys
        try:
            selected = int(selected) if selected is not None else None
        except (TypeError, ValueError):
            selected = None
        correct_index = q.get("correct", 0)
        is_correct = selected is not None and selected == correct_index
        if is_correct:
            correct_count += 1
        results.append({
            "selected": selected,
            "correct": correct_index,
            "is_correct": is_correct,
        })

    score = round((correct_count / total) * 100) if total else 0
    passed = score >= (exam.pass_percent or 0)

    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=current_user.id,
        course_id=exam.course_id,
        score=score,
        correct_count=correct_count,
        total_questions=total,
        passed=passed,
        answers={str(k): v for k, v in answers.items()},
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "score": score,
        "correct_count": correct_count,
        "total_questions": total,
        "passed": passed,
        "pass_percent": exam.pass_percent,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
#  ADMIN / TEAM ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/courses/{course_id}/exams")
def admin_list_exams(
    course_id: int,
    admin: User = Depends(get_current_owner_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    exams = (
        db.query(Exam)
        .filter(Exam.course_id == course_id)
        .order_by(Exam.sort_order.asc(), Exam.id.asc())
        .all()
    )
    return [_serialize_admin_exam(exam) for exam in exams]


@router.get("/admin/exams/{exam_id}")
def admin_get_exam(
    exam_id: int,
    admin: User = Depends(get_current_owner_user),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return _serialize_admin_exam(exam)


@router.post("/admin/courses/{course_id}/exams", status_code=201)
def admin_create_exam(
    course_id: int,
    data: ExamCreate,
    admin: User = Depends(get_current_owner_user),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if not data.title.strip():
        raise HTTPException(status_code=400, detail="Exam title is required")

    # Place the new exam at the end
    max_order = (
        db.query(Exam.sort_order)
        .filter(Exam.course_id == course_id)
        .order_by(Exam.sort_order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    pass_percent = data.pass_percent if data.pass_percent is not None else 70
    pass_percent = max(0, min(100, pass_percent))

    exam = Exam(
        course_id=course_id,
        title=data.title.strip(),
        description=data.description,
        pass_percent=pass_percent,
        questions=_normalize_questions(data.questions),
        is_published=data.is_published,
        sort_order=next_order,
        after_lesson_id=_validate_after_lesson(db, course_id, data.after_lesson_id),
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _serialize_admin_exam(exam)


@router.patch("/admin/exams/{exam_id}")
def admin_update_exam(
    exam_id: int,
    data: ExamUpdate,
    admin: User = Depends(get_current_owner_user),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    update_data = data.model_dump(exclude_unset=True)

    if "title" in update_data:
        title = (update_data["title"] or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Exam title is required")
        exam.title = title
    if "description" in update_data:
        exam.description = update_data["description"]
    if "pass_percent" in update_data and update_data["pass_percent"] is not None:
        exam.pass_percent = max(0, min(100, update_data["pass_percent"]))
    if "questions" in update_data and update_data["questions"] is not None:
        exam.questions = _normalize_questions(data.questions)
    if "is_published" in update_data and update_data["is_published"] is not None:
        exam.is_published = update_data["is_published"]
    if "sort_order" in update_data and update_data["sort_order"] is not None:
        exam.sort_order = update_data["sort_order"]
    if "after_lesson_id" in update_data:
        exam.after_lesson_id = _validate_after_lesson(db, exam.course_id, update_data["after_lesson_id"])

    db.commit()
    db.refresh(exam)
    return _serialize_admin_exam(exam)


@router.delete("/admin/exams/{exam_id}", status_code=204)
def admin_delete_exam(
    exam_id: int,
    admin: User = Depends(get_current_owner_user),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    db.delete(exam)
    db.commit()
    return None
