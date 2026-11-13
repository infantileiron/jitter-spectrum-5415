import uuid,redis
from fastapi import HTTPException
from src.models import ComparisonRun,ComparisonStudy
from src.config.settings import REDIS_URL
from src.utils.time import now
from src.utils.serialization import serialize
QUEUE="jitter-spectrum:comparison-jobs"
def create(db,study_id):
 if not db.get(ComparisonStudy,study_id):raise HTTPException(404,"对照研究不存在")
 item=ComparisonRun(id=str(uuid.uuid4()),study_id=study_id,status="queued",result={},error="",created_at=now())
 db.add(item);db.commit()
 try:redis.Redis.from_url(REDIS_URL).lpush(QUEUE,item.id)
 except redis.RedisError:
  item.status="failed";item.error="后台队列不可用，请重试";db.commit();raise HTTPException(503,item.error)
 return serialize(item)
