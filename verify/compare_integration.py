#!/usr/bin/env python3
# 集成验证：用模拟 dataset/window/study 对象走 analyze_comparison 编排，
# 复刻 seed_demo 的链路结构，确认演示数据能产出预期状态（含证据不足示例）。
import math,random,sys
sys.path.insert(0,"backend")
from src.services.comparison_studies import analyze_comparison
rng=random.Random(2307)
class DS:id="demo-data"
class Window:
 def __init__(self,wid,link):
  self.id=wid;self.link_id=link;self.dataset_id="demo-data"
  self.start_minutes=0.0;self.end_minutes=1e9
class Study:
 def __init__(self,ids,detrend,fp):
  self.window_ids=ids;self.detrend=detrend
  self.min_frequency=.005;self.max_frequency=.1;self.frequency_points=fp
# 复刻种子：6链路各480点
points=[]
for link in range(1,7):
 for i in range(480):
  t=float(i)
  if link==3:t+=int(i>=120)+int(i>=240)+int(i>=360)
  if link==4 and i>0:t+=rng.uniform(-.2,.2)
  value=12+math.sin(2*math.pi*t/30)+.5*math.cos(2*math.pi*t/80)+rng.gauss(0,.025)
  if link==2:value+=.009*t
  if link==5:value=10+1.2*math.sin(2*math.pi*t/45)+.4*math.cos(2*math.pi*t/120)
  if link==6:value=14
  points.append({"link_id":f"BY-{link:02}","time_minutes":round(t,6),"jitter_ms":round(value,8)})
dataset=DS();dataset.points=points
windows={f"demo-window-{k}":Window(f"demo-window-{k}",f"BY-{k:02}") for k in range(1,7)}
class DB:
 def get(self,cls,key):
  if cls.__name__=="SamplingWindow":return windows[key]
  if cls.__name__=="SignalDataset":return dataset
# 修正窗口边界为真实范围（模拟 seed 中按实际点设定）
for w in windows.values():
 pts=[p for p in points if p["link_id"]==w.link_id]
 w.start_minutes=min(p["time_minutes"] for p in pts);w.end_minutes=max(p["time_minutes"] for p in pts)
db=DB();fails=[]
def check(n,c,d=""):
 print(("PASS" if c else "FAIL"),n,d);
 if not c:fails.append(n)
# 主对照：BY-01..04（含缺点 BY-03、抖动 BY-04）
main=Study(["demo-window-1","demo-window-2","demo-window-3","demo-window-4"],"linear",1400)
r=analyze_comparison(db,main)
check("主对照 completed",r["status"]=="completed",r.get("conclusion"))
if r["status"]=="completed":
 sf=r["shared_frequency"]
 check("共享周期≈30分钟",abs(sf["period_minutes"]-30)<0.5,str(sf["period_minutes"]))
 check("4链路全部参与",len([l for l in r["links"] if l.get("usable")])==4)
 check("含两两相位差",len(r["phase_differences"])==6)
 check("统一原点=共同覆盖起点",sf["phase_origin_minutes"]==r["overlap_start_minutes"])
 check("每链路有趋势/振幅/相位",all("amplitude_ms" in l and "slope_ms_per_minute" in l and "phase_radians" in l for l in r["links"] if l.get("usable")))
 check("残差不补点 BY-03",len(next(l for l in r["links"] if l["link_id"]=="BY-03")["observations"])==
       len([p for p in points if p["link_id"]=="BY-03" and r["overlap_start_minutes"]<=p["time_minutes"]<=r["overlap_end_minutes"]]))
 check("有checksum",len(r.get("checksum",""))==64)
# 弱证据：BY-05(45/120) 与 BY-06(常量)
weak=Study(["demo-window-5","demo-window-6"],"mean",1200)
rw=analyze_comparison(db,weak)
check("弱证据不给同步结论",rw["status"] in ("insufficient_evidence","insufficient_samples") and rw["shared_frequency"] is None,rw.get("conclusion"))
check("弱证据有原因说明",len(rw.get("reasons",[]))>0 or any(l.get("reason") for l in rw.get("links",[])))
print("INTEGRATION:", "ALL PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
