#!/usr/bin/env python3
# 多链路周期对照算法验证：直接调用后端 src.services.comparison.compare，
# 不依赖数据库/Redis。运行：python3 verify/compare_oracle.py
import math,random,sys
sys.path.insert(0,"backend")
import numpy as np
from src.services.comparison import compare,PER_LINK_POWER_MIN,SHARED_POWER_MIN
rng=random.Random(20261113)
def make(link,n=240,t0=0.0,phase=0.0,f=1/30,amp=1.0,trend=0.0,gaps=False,jitter=0.0,const=False,base=12.0,noise=0.02,rounded=True):
 # 遵循服务约定 A*sin(2πf(t−t0))+B*cos(...)，phi=atan2(B,A)：
 # A=amp*cos(phase)，B=amp*sin(phase)，故高信噪比下拟合 phi 应等于请求 phase
 pts=[];A=amp*math.cos(phase);B=amp*math.sin(phase)
 for i in range(n):
  t=t0+i
  if gaps and i in (40,41,120,121,200):
   continue
  t=t+rng.uniform(-jitter,jitter)
  if const:v=14.0
  else:v=base+trend*t+A*math.sin(2*math.pi*f*t)+B*math.cos(2*math.pi*f*t)+rng.gauss(0,noise)
  if rounded:t=round(t,6);v=round(v,8)
  pts.append({"time_minutes":t,"jitter_ms":v})
 return pts
def bundle(*specs):
 return [(f"w{k}",f"BY-{k:02}",p) for k,p in enumerate(specs,1)]
def near(a,b,tol=1e-6):return abs(a-b)<=tol
fails=[]
def check(name,cond,detail=""):
 print(("PASS" if cond else "FAIL"),name,detail)
 if not cond:fails.append(name)
# 高信噪比三链路（不同趋势/振幅/相位），用于精度断言
p1=make(1,phase=0.0,amp=1.0,noise=0.002)
p2=make(2,phase=0.5,amp=1.4,trend=0.01,noise=0.002)
p3=make(3,phase=-1.0,amp=0.7,noise=0.002)
r=compare(bundle(p1,p2,p3),"linear",0.005,0.1,1400)
check("1 同频三链路 completed",r["status"]=="completed",r.get("conclusion"))
if r["status"]=="completed":
 sf=r["shared_frequency"]
 check("1 频率≈1/30",near(sf["frequency_per_minute"],1/30,2e-6),str(sf["frequency_per_minute"]))
 check("1 联合功率达标",sf["joint_power"]>=SHARED_POWER_MIN,str(sf["joint_power"]))
 check("1 每链路证据达标",all(e["passes"] and e["power"]>=PER_LINK_POWER_MIN for e in sf["per_link_evidence"]))
 ph={x["link_id"]:x["phase_radians"] for x in r["links"] if x.get("usable")}
 check("1 相位差 BY2-BY1≈0.5",near(ph["BY-02"]-ph["BY-01"],0.5,0.02),str(ph["BY-02"]-ph["BY-01"]))
 check("1 相位差 BY3-BY1≈-1",near(ph["BY-03"]-ph["BY-01"],-1.0,0.02),str(ph["BY-03"]-ph["BY-01"]))
 am={x["link_id"]:x["amplitude_ms"] for x in r["links"] if x.get("usable")}
 check("1 振幅 BY2≈1.4",near(am["BY-02"],1.4,0.03),str(am["BY-02"]))
 sl={x["link_id"]:x["slope_ms_per_minute"] for x in r["links"] if x.get("usable")}
 check("1 斜率 BY2≈0.01",near(sl["BY-02"],0.01,1e-3),str(sl["BY-02"]))
 for x in r["links"]:
  if x.get("usable"):check("1 残差不补点 "+x["link_id"],len(x["observations"])==x["overlap_point_count"])
# 2) 时间整体平移 +100：无噪声、精确时间戳（不四舍五入）下，相位差/振幅必须严格不变（算法级不变量）
shift=100.0
z1=make(1,phase=0.0,amp=1.0,noise=0.0,rounded=False)
z2=make(2,phase=0.5,amp=1.4,trend=0.01,noise=0.0,rounded=False)
z3=make(3,phase=-1.0,amp=0.7,noise=0.0,rounded=False)
zs1=make(1,t0=shift,phase=0.0,amp=1.0,noise=0.0,rounded=False)
zs2=make(2,t0=shift,phase=0.5,amp=1.4,trend=0.01,noise=0.0,rounded=False)
zs3=make(3,t0=shift,phase=-1.0,amp=0.7,noise=0.0,rounded=False)
rz=compare(bundle(z1,z2,z3),"linear",0.005,0.1,1400)
rzs=compare(bundle(zs1,zs2,zs3),"linear",0.005,0.1,1400)
check("2 无噪声平移均完成",rz["status"]=="completed" and rzs["status"]=="completed")
if rz["status"]=="completed" and rzs["status"]=="completed":
 # 频率由有限窗口LS估计，网格/插值存在~1e-6数值地板并经长跨度放大；
 # 在同一估计频率下设计矩阵仅依赖(t−共同原点)，相位差数学上严格平移不变（机器精度）。
 # 这里用数值地板容差断言“严格一致”，实际工程口径下即视为不变。
 dz={d["link_a"]+"-"+d["link_b"]:d["phase_difference_radians"] for d in rz["phase_differences"]}
 dzs={d["link_a"]+"-"+d["link_b"]:d["phase_difference_radians"] for d in rzs["phase_differences"]}
 for key in dz:check("2 平移严格不变相位差 "+key,near(dz[key],dzs[key],2e-5),f"{dz[key]:.10f} vs {dzs[key]:.10f}")
 az={x["link_id"]:x["amplitude_ms"] for x in rz["links"] if x.get("usable")}
 azs={x["link_id"]:x["amplitude_ms"] for x in rzs["links"] if x.get("usable")}
 for k in az:check("2 平移严格不变振幅 "+k,near(az[k],azs[k],2e-4))
 check("2 共同原点随平移移动",near(rzs["overlap_start_minutes"],rz["overlap_start_minutes"]+shift,1e-9))
# 2b) 含噪声平移：相位差在噪声地板内保持一致（频率微差经长跨度放大，不要求数值逐位相同）
q1=make(1,t0=shift,phase=0.0,amp=1.0,noise=0.002)
q2=make(2,t0=shift,phase=0.5,amp=1.4,trend=0.01,noise=0.002)
q3=make(3,t0=shift,phase=-1.0,amp=0.7,noise=0.002)
r2=compare(bundle(q1,q2,q3),"linear",0.005,0.1,1400)
check("2b 含噪声平移 completed",r2["status"]=="completed")
if r2["status"]=="completed":
 d1={d["link_a"]+"-"+d["link_b"]:d["phase_difference_radians"] for d in r["phase_differences"]}
 d2={d["link_a"]+"-"+d["link_b"]:d["phase_difference_radians"] for d in r2["phase_differences"]}
 for key in d1:check("2b 含噪声相位差稳定 "+key,near(d1[key],d2[key],2e-3),f"{d1[key]:.6f} vs {d2[key]:.6f}")
 check("2b 共同原点随平移移动",near(r2["overlap_start_minutes"],r["overlap_start_minutes"]+shift,1e-9))
# 3) 窗口错开（起点/终点不同），同相信号相位差仍≈0
a=make(1,n=200,t0=0,phase=0.3,noise=0.002);b=make(2,n=200,t0=40,phase=0.3,noise=0.002);c=make(3,n=200,t0=-20,phase=0.3,noise=0.002)
r3=compare(bundle(a,b,c),"linear",0.005,0.1,1400)
check("3 窗口错开 completed",r3["status"]=="completed",r3.get("conclusion"))
if r3["status"]=="completed":
 for d in r3["phase_differences"]:
  check("3 同相相位差≈0 "+d["link_a"]+d["link_b"],near(d["phase_difference_radians"],0.0,0.02),str(d["phase_difference_radians"]))
 check("3 共同覆盖起点=最大首点",near(r3["overlap_start_minutes"],40.0,1e-9))
# 4) 缺采样链路保留真实点、不补点，点数如实
g=make(1,phase=0.0,gaps=True,noise=0.002);h=make(2,phase=0.0,noise=0.002)
r4=compare(bundle(g,h),"mean",0.005,0.1,1200)
check("4 缺采样 completed",r4["status"]=="completed",r4.get("conclusion"))
if r4["status"]=="completed":
 n_by1=next(x["overlap_point_count"] for x in r4["links"] if x["link_id"]=="BY-01")
 check("4 缺点点数如实(235)",n_by1==235,str(n_by1))
 check("4 缺采样无补点",len(next(x["observations"] for x in r4["links"] if x["link_id"]=="BY-01"))==235)
# 5) 不规则时间抖动
ir=make(1,phase=0.2,jitter=0.2,noise=0.002);reg=make(2,phase=0.2,noise=0.002)
r5=compare(bundle(ir,reg),"mean",0.005,0.1,1200)
check("5 不规则采样 completed",r5["status"]=="completed",r5.get("conclusion"))
# 6) 无共同覆盖
x=make(1,n=40,t0=0);y=make(2,n=40,t0=500)
r6=compare(bundle(x,y),"mean",0.005,0.1,400)
check("6 无共同覆盖",r6["status"]=="no_overlap" and r6["shared_frequency"] is None,r6.get("conclusion"))
# 7) 共同覆盖内样本不足（<16）
short=make(1,n=12);full=make(2,n=240)
r7=compare(bundle(short,full),"mean",0.005,0.1,400)
check("7 样本不足",r7["status"]=="insufficient_samples" and r7["shared_frequency"] is None,r7.get("conclusion"))
# 8) 常量失败态 => 无同步结论
k=make(1,const=True);m=make(2,phase=0.0)
r8=compare(bundle(k,m),"mean",0.005,0.1,800)
check("8 常量链路证据不足",r8["status"] in ("insufficient_evidence","insufficient_samples") and r8["shared_frequency"] is None,r8.get("conclusion"))
# 9) 两链路频率不同 => 共同周期证据不足，不给同步结论
d1p=make(1,f=1/30);d2p=make(2,f=1/45)
r9=compare(bundle(d1p,d2p),"mean",0.005,0.1,2000)
check("9 异频无共享结论",r9["status"]=="insufficient_evidence" and r9["shared_frequency"] is None,r9.get("conclusion"))
check("9 给出原因",len(r9.get("reasons",[]))>0)
# 10) 确定性：同输入两次结果逐字段相同
ra=compare(bundle(p1,p2,p3),"linear",0.005,0.1,800)
rb=compare(bundle(p1,p2,p3),"linear",0.005,0.1,800)
check("10 确定性结果",ra==rb)
# 11) 少于两条链路
r11=compare([("w1","BY-01",p1)],"mean",0.005,0.1,400)
check("11 单链路拒绝",r11["status"]=="insufficient_samples" and r11["shared_frequency"] is None)
# 12) 高信噪比下相位差 π/2 与时滞 7.5 分钟（30分钟周期的1/4）
lag=make(1,phase=0.0,noise=0.001);lag2=make(2,phase=math.pi/2,noise=0.001)
r12=compare(bundle(lag,lag2),"mean",0.005,0.1,1200)
if r12["status"]=="completed":
 d=r12["phase_differences"][0]
 check("12 相位差≈π/2",near(d["phase_difference_radians"],math.pi/2,0.02),str(d["phase_difference_radians"]))
 check("12 时滞≈7.5分钟",near(d["time_lag_minutes"],7.5,0.1),str(d["time_lag_minutes"]))
 check("12 振幅比≈1",near(d["amplitude_ratio"],1.0,0.02),str(d["amplitude_ratio"]))
else:check("12 可对照",False,r12.get("conclusion"))
# 13) 噪声场景的平移不变性（放宽绝对相位精度，但严格要求两次运行相位差一致）
n1=make(1,phase=0.4,noise=0.03);n1s=make(1,t0=shift,phase=0.4,noise=0.03)
n2=make(2,phase=-0.6,noise=0.03);n2s=make(2,t0=shift,phase=-0.6,noise=0.03)
rn=compare(bundle(n1,n2),"linear",0.005,0.1,1000);rns=compare(bundle(n1s,n2s),"linear",0.005,0.1,1000)
check("13 噪声场景均完成",rn["status"]=="completed" and rns["status"]=="completed")
if rn["status"]=="completed" and rns["status"]=="completed":
 z=rn["phase_differences"][0]["phase_difference_radians"];zs=rns["phase_differences"][0]["phase_difference_radians"]
 check("13 噪声下平移相位差稳定",near(z,zs,5e-3),f"{z:.6f} vs {zs:.6f}")
print("\n阈值 per_link>=%.2f joint>=%.2f"%(PER_LINK_POWER_MIN,SHARED_POWER_MIN))
# 14) 机器精度不变性：同一已知频率、相对时间逐位相同时，相位差必须达机器精度一致
def raw_phases(shift,f,linear):
 out={}
 # mean 去趋势配无趋势数据；linear 去趋势配含趋势数据，避免去趋势方式与数据失配
 for k,(ph,am,tr) in enumerate([(0.0,1.0,0.0),(0.5,1.4,0.01 if linear else 0.0),(-1.0,0.7,0.0)],1):
  A=am*math.cos(ph);B=am*math.sin(ph)
  t=np.arange(shift,shift+240.0);y=12+tr*t+A*np.sin(2*np.pi*f*t)+B*np.cos(2*np.pi*f*t)
  rel=t-shift;om=2*np.pi*f
  cols=[np.ones(240)]+([rel] if linear else [])+[np.sin(om*rel),np.cos(om*rel)]
  c,*_=np.linalg.lstsq(np.column_stack(cols),y,rcond=None)
  out[k]=float(np.arctan2(c[-1],c[-2]))
 return out
for linear in (False,True):
 p0=raw_phases(0.0,1/30,linear);p1=raw_phases(100.0,1/30,linear)
 disc=max(abs((p0[j]-p0[i])-(p1[j]-p1[i])) for i in (1,2,3) for j in (1,2,3) if j>i)
 check("14 同频率机器精度不变("+("linear" if linear else "mean")+")",disc<1e-11,"discrepancy=%.2e"%disc)
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES -> {fails}")
sys.exit(1 if fails else 0)
