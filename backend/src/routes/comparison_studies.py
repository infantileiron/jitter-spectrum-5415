from fastapi import APIRouter,Depends
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import ComparisonStudy
from src.schemas.comparison import ComparisonStudyInput
from src.services import comparison_studies as service
from src.utils.serialization import rows
router=APIRouter(prefix="/comparison-studies")
@router.get("")
def listing(db=Depends(db_session),user=Depends(current_user)):
 return rows(db.scalars(select(ComparisonStudy).order_by(ComparisonStudy.created_at.desc())))
@router.post("")
def create(payload:ComparisonStudyInput,db=Depends(db_session),user=Depends(writer)):
 return service.create_study(db,payload)
