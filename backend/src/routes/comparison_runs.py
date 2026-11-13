from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import ComparisonRun
from src.schemas.comparison import ComparisonRunInput
from src.services import comparison_runs as service
from src.utils.serialization import rows,serialize
router=APIRouter(prefix="/comparison-runs")
@router.get("")
def listing(db=Depends(db_session),user=Depends(current_user)):
 return rows(db.scalars(select(ComparisonRun).order_by(ComparisonRun.created_at.desc())))
@router.post("")
def create(payload:ComparisonRunInput,db=Depends(db_session),user=Depends(writer)):
 return service.create(db,payload.study_id)
@router.get("/{id}")
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):
 item=db.get(ComparisonRun,id)
 if not item:raise HTTPException(404,"对照运行不存在")
 return serialize(item)
