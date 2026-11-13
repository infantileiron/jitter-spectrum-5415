import hashlib,json,uuid
from sqlalchemy import select
from fastapi import HTTPException
from src.models import ComparisonStudy,SamplingWindow,SignalDataset
from src.services.windows import points_for
from src.services.comparison import compare
from src.utils.time import now
from src.utils.serialization import serialize
def analyze_comparison(db,study):
 windows=[]
 for wid in study.window_ids:
  window=db.get(SamplingWindow,wid)
  if not window:raise ValueError("采样窗口 %s 不存在"%wid)
  dataset=db.get(SignalDataset,window.dataset_id)
  windows.append((window.id,window.link_id,points_for(dataset,window)))
 link_ids=[w[1] for w in windows]
 if len(set(link_ids))!=len(link_ids):raise ValueError("对照研究的每个窗口必须来自不同链路")
 result=compare(windows,study.detrend,study.min_frequency,study.max_frequency,study.frequency_points)
 payload=[{"window_id":wid,"link_id":lid,"n":len(pts)} for wid,lid,pts in windows]
 result["checksum"]=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
 return result
def create_study(db,payload):
 ids=payload.window_ids
 if len(ids)<2:raise HTTPException(422,"多链路对照至少选择2个窗口")
 if len(ids)>12:raise HTTPException(422,"一次对照最多12条链路")
 if len(set(ids))!=len(ids):raise HTTPException(422,"窗口不能重复选择")
 windows=[db.get(SamplingWindow,i) for i in ids]
 if any(w is None for w in windows):raise HTTPException(404,"存在不存在的采样窗口")
 links=[w.link_id for w in windows]
 if len(set(links))!=len(links):raise HTTPException(422,"每个窗口必须来自不同链路，同链路窗口不能互相对照")
 datasets={w.dataset_id for w in windows}
 if len(datasets)!=1:raise HTTPException(422,"对照窗口必须来自同一观测集，时间口径才能对齐")
 overlap_start=max(w.start_minutes for w in windows)
 overlap_end=min(w.end_minutes for w in windows)
 if overlap_end<=overlap_start:
  raise HTTPException(422,"所选窗口没有共同覆盖时段，无法联合寻找共享频率；不做外推或补点")
 # 共同覆盖内每条链路的真实点数与跨度（缺采样不补点）
 min_span=None
 for w in windows:
  dataset=db.get(SignalDataset,w.dataset_id)
  pts=[p for p in points_for(dataset,w) if overlap_start<=p["time_minutes"]<=overlap_end]
  if len(pts)<16:raise HTTPException(422,"链路 %s 在共同覆盖内仅%d点（<16），样本不足不做对照"%(w.link_id,len(pts)))
  span=pts[-1]["time_minutes"]-pts[0]["time_minutes"]
  min_span=span if min_span is None else min(min_span,span)
 if payload.min_frequency<1/min_span*(1-1e-9):
  raise HTTPException(422,"最大搜索周期不能超过共同覆盖实际跨度 %.3f 分钟"%min_span)
 if db.scalar(select(ComparisonStudy).where(ComparisonStudy.name==payload.name)):
  raise HTTPException(409,"对照研究名称已存在")
 item=ComparisonStudy(id=str(uuid.uuid4()),created_at=now(),**payload.model_dump())
 db.add(item);db.commit()
 return serialize(item)
