from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ml.adapter import ModelNotReady
from app.schemas.detection import BatchDetectionRequest, DetectionSubmitResponse, SingleDetectionRequest, TaskStatusResponse
from app.services.detection import DetectionService

router = APIRouter(prefix="/api/v1", tags=["detection"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/detections", response_model=DetectionSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_detection(request: SingleDetectionRequest, db: Session = Depends(get_db)):
    try:
        return DetectionService(db).submit_single(request)
    except (ModelNotReady, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/detections/batch", response_model=list[DetectionSubmitResponse], status_code=status.HTTP_202_ACCEPTED)
def submit_batch(request: BatchDetectionRequest, db: Session = Depends(get_db)):
    service = DetectionService(db)
    responses = []
    try:
        for item in request.items:
            responses.append(service.submit_single(item))
        return responses
    except (ModelNotReady, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/detections/{task_id}", response_model=TaskStatusResponse)
def get_detection_status(task_id: str, db: Session = Depends(get_db)):
    result = DetectionService(db).status(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="task not found")
    return result
