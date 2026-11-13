#!/usr/bin/env python3
# 端到端 HTTP 测试：TestClient + sqlite，mock Redis 队列，手动驱动 worker。
import os,sys
os.environ["DATABASE_URL"]="sqlite:////tmp/e2e.db";os.environ["SEED_DEMO"]="false";os.environ["REDIS_URL"]="redis://localhost:6379/0"
sys.path.insert(0,"backend")
import redis as _redis
from src.config.database import Base,engine,Session
from src.models import ComparisonRun
from scripts.seed_demo import seed
captured=[]
class FakeRedis:
 def lpush(self,queue,id):captured.append((queue,id));return 1
 def ping(self):return True
def _fake_from_url(url=None,*a,**k):return FakeRedis()
_redis.Redis.from_url=_fake_from_url
from fastapi.testclient import TestClient
from src.main import app
Base.metadata.create_all(engine);seed()
client=TestClient(app)
def login(email):
 r=client.post("/auth/login",json={"email":email,"password":"Signal2026!"});assert r.status_code==200,r.text
 return r.json()["token"]
admin=login("admin@beiyu.demo");viewer=login("viewer@beiyu.demo")
H={"Authorization":"Bearer "+admin};HV={"Authorization":"Bearer "+viewer}
fails=[]
def check(n,c,d=""):
 print(("PASS" if c else "FAIL"),n,d);
 if not c:fails.append(n)
# viewer 禁止创建
r=client.post("/comparison-studies",headers=HV,json={"name":"viewer-attempt","window_ids":["demo-window-1","demo-window-2"],"min_frequency":.005,"max_frequency":.1})
check("viewer 403",r.status_code==403,str(r.status_code))
# admin 建立对照（BY-01..04）
payload={"name":"E2E多链路对照","window_ids":["demo-window-1","demo-window-2","demo-window-3","demo-window-4"],"detrend":"linear","min_frequency":.005,"max_frequency":.1,"frequency_points":1000}
r=client.post("/comparison-studies",headers=H,json=payload);check("创建对照研究 200",r.status_code==200,r.text)
sid=r.json()["id"]
r=client.get("/comparison-studies",headers=H);check("对照研究列表",r.status_code==200 and len(r.json())>=1)
# 触发运行（redis 被 mock，任务入 captured）
r=client.post("/comparison-runs",headers=H,json={"study_id":sid});check("触发对照运行 200",r.status_code==200,r.text)
run_id=r.json()["id"];check("任务进入对照队列",captured and captured[-1][0]=="jitter-spectrum:comparison-jobs")
# 手动驱动 worker 的对照执行函数（绕过真实 redis brpop）
from src.worker import execute_comparison
execute_comparison(run_id)
with Session() as db:
 run=db.get(ComparisonRun,run_id)
 check("worker 计算 completed",run.status=="completed",run.error)
 res=run.result
 check("找到共享频率",res["shared_frequency"] is not None and abs(res["shared_frequency"]["period_minutes"]-30)<1)
 check("4链路结果",len([l for l in res["links"] if l.get("usable")])==4)
 check("含相位差",len(res["phase_differences"])==6)
# GET 详情
r=client.get("/comparison-runs/"+run_id,headers=H);check("运行详情 200",r.status_code==200 and r.json()["result"]["status"]=="completed")
r=client.get("/comparison-runs",headers=H);check("运行列表",r.status_code==200 and any(x["id"]==run_id for x in r.json()))
# 弱证据对照（BY-05/06）应完成但无共享结论
r=client.post("/comparison-studies",headers=H,json={"name":"E2E弱证据","window_ids":["demo-window-5","demo-window-6"],"detrend":"mean","min_frequency":.005,"max_frequency":.1,"frequency_points":800})
wid=r.json()["id"]
r=client.post("/comparison-runs",headers=H,json={"study_id":wid});weak_id=r.json()["id"];execute_comparison(weak_id)
with Session() as db:
 wres=db.get(ComparisonRun,weak_id).result
 check("弱证据无同步结论",wres["shared_frequency"] is None and wres["status"] in ("insufficient_evidence","insufficient_samples"),wres["status"])
# 原单链路接口不受影响
r=client.get("/runs",headers=H);legacy=r.json();check("原单链路运行保留",any(x["id"]=="demo-run" and x["result"].get("fit") for x in legacy))
r=client.get("/runs/demo-run",headers=H);check("原单链路详情可查",r.status_code==200 and r.json()["result"]["fit"]["components"])
print("E2E:", "ALL PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
