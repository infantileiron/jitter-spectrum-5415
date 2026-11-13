from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import SpectralRun,SpectralStudy,SamplingWindow,SignalDataset,ComparisonRun,ComparisonStudy
from src.services.windows import points_for
from src.services.analysis import analyze
from src.services.comparison_studies import analyze_comparison
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path("/artifacts/worker-heartbeat")
SINGLE_QUEUE="jitter-spectrum:jobs"
COMPARISON_QUEUE="jitter-spectrum:comparison-jobs"
def execute_single(id):
 with Session() as db:
  run=db.get(SpectralRun,id)
  if not run or run.status not in ("queued","running"):return
  run.status="running";db.commit()
  try:
   study=db.get(SpectralStudy,run.study_id);window=db.get(SamplingWindow,study.window_id);dataset=db.get(SignalDataset,window.dataset_id)
   run.result=analyze(points_for(dataset,window),study);run.status="completed"
  except Exception as e:run.error=str(e);run.status="failed";traceback.print_exc()
  db.commit()
def execute_comparison(id):
 with Session() as db:
  run=db.get(ComparisonRun,id)
  if not run or run.status not in ("queued","running"):return
  run.status="running";db.commit()
  try:
   study=db.get(ComparisonStudy,run.study_id)
   run.result=analyze_comparison(db,study);run.status="completed"
  except Exception as e:run.error=str(e);run.status="failed";traceback.print_exc()
  db.commit()
def recover_and_serve():
 with Session() as db:
  for id in db.scalars(select(SpectralRun.id).where(SpectralRun.status.in_(["queued","running"]))):client.lpush(SINGLE_QUEUE,id)
  for id in db.scalars(select(ComparisonRun.id).where(ComparisonRun.status.in_(["queued","running"]))):client.lpush(COMPARISON_QUEUE,id)
 while True:
  heartbeat.touch();job=client.brpop([SINGLE_QUEUE,COMPARISON_QUEUE],timeout=1)
  if not job:continue
  queue,raw=job;id=raw.decode()
  if queue.decode()==COMPARISON_QUEUE:execute_comparison(id)
  else:execute_single(id)
if __name__=="__main__":recover_and_serve()
