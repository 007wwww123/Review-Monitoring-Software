from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from datetime import date, datetime, timezone
import csv, io
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ml.adapter import ModelNotReady
from app.schemas.auth import (CurrentUserResponse, LoginRequest, LoginResponse,
                              PasswordChangeRequest, UserCreateRequest,
                              UserResponse)
from app.schemas.admin import EvaluationRequest, EvaluationResponse, ModelResponse, ReportRequest, ReportResponse, ResultPage, ResultResponse
from app.schemas.detection import BatchDetectionRequest, DetectionSubmitResponse, SingleDetectionRequest, SingleDetectionResponse, TaskStatusResponse
from app.models import SysUser, DetectionResult
from app.security import (create_access_token, current_user, hash_password,
                          require_admin, verify_password)
from app.services.admin import AdminService
from app.services.detection import DetectionService

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@router.post("/auth/login", response_model=LoginResponse, tags=["auth"])
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(SysUser).where(SysUser.username == request.username))
    if user is None or user.status != "active" or not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "invalid username or password")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    token, expires = create_access_token(user)
    return LoginResponse(user_id=user.id, username=user.username, role=user.role, access_token=token, expires_at=expires)

@router.post("/auth/logout", status_code=204, tags=["auth"])
def logout(_: SysUser = Depends(current_user)):
    return Response(status_code=204)

@router.get("/auth/me", response_model=CurrentUserResponse, tags=["auth"])
def auth_me(user: SysUser = Depends(current_user)):
    return CurrentUserResponse(user_id=user.id, username=user.username, display_name=user.display_name, role=user.role, status=user.status, last_login_at=user.last_login_at)

@router.put("/auth/password", status_code=204, tags=["auth"])
def change_password(request: PasswordChangeRequest, db: Session = Depends(get_db), user: SysUser = Depends(current_user)):
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if verify_password(request.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="new password must be different")
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return Response(status_code=204)

@router.post("/users", response_model=UserResponse, status_code=201, tags=["users"])
def create_user(request: UserCreateRequest, db: Session = Depends(get_db), _: SysUser = Depends(require_admin)):
    if db.scalar(select(SysUser.id).where(SysUser.username == request.username)) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = SysUser(username=request.username, display_name=request.display_name, password_hash=hash_password(request.password), role=request.role, status="active")
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(user_id=user.id, username=user.username, display_name=user.display_name, role=user.role, status=user.status, created_at=user.created_at)


@router.post("/detections", response_model=SingleDetectionResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/detections/single", response_model=SingleDetectionResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_detection(request: SingleDetectionRequest, db: Session = Depends(get_db)):
    try:
        return DetectionService(db).submit_single(request)
    except (ModelNotReady, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/detections/batch", response_model=DetectionSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_batch(request: BatchDetectionRequest, db: Session = Depends(get_db)):
    try:
        return DetectionService(db).submit_batch(request.items)
    except (ModelNotReady, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/detections/{task_id}", response_model=TaskStatusResponse)
def get_detection_status(task_id: str, db: Session = Depends(get_db)):
    result = DetectionService(db).status(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="task not found")
    return result

@router.get("/tasks/{task_id}", response_model=TaskStatusResponse, tags=["tasks"])
def task_status(task_id: str, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    return get_detection_status(task_id, db)

@router.get("/tasks/{task_id}/results", response_model=ResultPage, tags=["results"])
def task_results(task_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    rows, total = DetectionService(db).repo.results(task_no=task_id, page=page, page_size=page_size)
    return ResultPage(items=[_result_response(row) for row in rows], page=page, page_size=page_size, total=total)

def _result_response(row: DetectionResult) -> ResultResponse:
    review = row.review_event
    proxy = bool((row.explanation or {}).get("behavior", {}).get("is_proxy_task", True))
    return ResultResponse(result_id=row.id, task_id=row.task.task_no, review_id=review.external_review_id, user_key=review.user_key, product_id=review.product_key, text_excerpt=review.review_text[:240], authenticity=row.authenticity_label, confidence=float(row.authenticity_probability), semantic_type=row.semantic_label, behavior_type=row.behavior_label, risk_source=(row.risk_source or {}).get("value", "uncertain"), action=row.recommendation or "review", model_version=row.model_version.version, data_source="real_model", is_mock=False, is_proxy_task=proxy, explanation=row.explanation, created_at=row.created_at)

@router.get("/results", response_model=ResultPage, tags=["results"])
def results(task_id: str | None = None, keyword: str | None = Query(None, max_length=200), authenticity: str | None = Query(None), action: str | None = Query(None), date_from: date | None = Query(None), date_to: date | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    rows, total = DetectionService(db).repo.results(task_no=task_id, keyword=keyword, authenticity=authenticity, action=action, date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    return ResultPage(items=[_result_response(row) for row in rows], page=page, page_size=page_size, total=total)

@router.get("/results/{result_id}", response_model=ResultResponse, tags=["results"])
def result(result_id: int, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    rows, _ = DetectionService(db).repo.results(result_id=result_id)
    if not rows: raise HTTPException(404, "result not found")
    return _result_response(rows[0])

@router.get("/models", response_model=list[ModelResponse], tags=["models"])
def models(db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    return [_model_response(item) for item in AdminService(db).models()]

def _model_response(item):
    return ModelResponse(version=item.version, model_name=item.model_name, tokenizer_name=item.tokenizer_name, config=item.config_json, metrics=item.metrics_json, checkpoint_sha256=item.checkpoint_sha256, is_active=item.is_active, created_at=item.created_at)

@router.get("/models/active", response_model=ModelResponse, tags=["models"])
def active_model(db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    item = db.scalar(select(type(AdminService(db).models()[0])) if AdminService(db).models() else select(SysUser))
    from app.repositories.detection import DetectionRepository
    item = DetectionRepository(db).active_model()
    if item is None: raise HTTPException(404, "active model not found")
    return _model_response(item)

@router.get("/models/{version}", response_model=ModelResponse, tags=["models"])
def model(version: str, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    item = AdminService(db).model(version)
    if item is None: raise HTTPException(404, "model not found")
    return _model_response(item)

@router.post("/models/{version}/activate", response_model=ModelResponse, tags=["models"])
def activate_model(version: str, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    try: item = AdminService(db).activate(version)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    if item is None: raise HTTPException(404, "model not found")
    return _model_response(item)

@router.post("/evaluations", response_model=EvaluationResponse, tags=["evaluations"])
def evaluation(request: EvaluationRequest, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    try: report = AdminService(db).evaluate(request)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    return EvaluationResponse(report_id=report.id, dataset_name=report.dataset_name, dataset_split=report.dataset_split, sample_count=report.sample_count, accuracy=report.accuracy, precision=report.precision_score, recall=report.recall_score, f1=report.f1_score, auc=report.auc_score, confusion_matrix=report.confusion_matrix, status=report.report_status, created_at=report.created_at)

@router.get("/evaluations", response_model=list[EvaluationResponse], tags=["evaluations"])
def evaluations(db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    rows = db.scalars(select(__import__("app.models", fromlist=["EvaluationReport"]).EvaluationReport).order_by(__import__("app.models", fromlist=["EvaluationReport"]).EvaluationReport.id.desc())).all()
    return [EvaluationResponse(report_id=r.id, dataset_name=r.dataset_name, dataset_split=r.dataset_split, sample_count=r.sample_count, accuracy=r.accuracy, precision=r.precision_score, recall=r.recall_score, f1=r.f1_score, auc=r.auc_score, confusion_matrix=r.confusion_matrix, status=r.report_status, created_at=r.created_at) for r in rows]

@router.get("/evaluations/{report_id}", response_model=EvaluationResponse, tags=["evaluations"])
def evaluation_detail(report_id: int, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    from app.models import EvaluationReport
    r = db.get(EvaluationReport, report_id)
    if r is None: raise HTTPException(404, "evaluation not found")
    return EvaluationResponse(report_id=r.id, dataset_name=r.dataset_name, dataset_split=r.dataset_split, sample_count=r.sample_count, accuracy=r.accuracy, precision=r.precision_score, recall=r.recall_score, f1=r.f1_score, auc=r.auc_score, confusion_matrix=r.confusion_matrix, status=r.report_status, created_at=r.created_at)

@router.post("/reports", response_model=ReportResponse, tags=["reports"])
def create_report(request: ReportRequest, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    result = AdminService(db).create_report(request.task_id)
    if result is None: raise HTTPException(404, "task not found")
    report, task = result
    return ReportResponse(report_id=report.id, task_id=task.task_no, status=report.status, summary=report.summary, created_at=report.created_at)

@router.get("/reports/{report_id}", response_model=ReportResponse, tags=["reports"])
def report(report_id: int, db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    item = db.get(__import__("app.models", fromlist=["ReportMetadata"]).ReportMetadata, report_id)
    if item is None: raise HTTPException(404, "report not found")
    task = db.get(__import__("app.models", fromlist=["DetectionTask"]).DetectionTask, item.task_id)
    return ReportResponse(report_id=item.id, task_id=task.task_no, status=item.status, summary=item.summary, created_at=item.created_at)

@router.get("/reports/{report_id}/download", tags=["reports"])
def download_report(report_id: int, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db), _: SysUser = Depends(current_user)):
    item = db.get(__import__("app.models", fromlist=["ReportMetadata"]).ReportMetadata, report_id)
    if item is None: raise HTTPException(404, "report not found")
    if format == "json": return JSONResponse(item.summary)
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["metric", "value"]); writer.writerows(item.summary.items())
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=report-{report_id}.csv"})
