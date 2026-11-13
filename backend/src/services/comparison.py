import math
import numpy as np
# 多链路周期对照：所有链路在共同覆盖时段内、按各自真实采样时刻联合寻找共享频率。
# 缺采样不补点、不重采样；相位以共同覆盖起点 t0 为统一绝对时间原点，
# 因而窗口错开或时间整体平移时，链路间相位差保持一致。
PER_LINK_POWER_MIN=0.20          # 每条参与链路在共享频率上的最低解释方差比例
SHARED_POWER_MIN=0.30            # 联合（加权）解释方差比例下限
MIN_LINKS=2
MIN_POINTS=16
def _detrend(t,y,detrend,t0):
 # 统一以共同覆盖起点 t0 为设计原点，保证去趋势结果对时间整体平移严格不变
 relative=t-t0
 if detrend=="linear":
  design=np.column_stack([np.ones(len(t)),relative])
  coef=np.linalg.lstsq(design,y,rcond=None)[0]
  baseline=design@coef
  return y-baseline,float(coef[0]),float(coef[1])
 if detrend!="mean":raise ValueError("去趋势方式只能为mean或linear")
 offset=float(np.mean(y))
 return y-offset,offset,0.0
def _link_power(t,y,detrend,frequency,t0):
 # 在原始观测上拟合 常数(+线性趋势)+sin+cos；设计矩阵只依赖 (t−t0)，
 # t0 统一为共同覆盖起点，因而频率/振幅/相位对所有链路时间整体平移严格不变。
 relative=t-t0;omega=2*np.pi*frequency
 columns=[np.ones(len(t))]
 if detrend=="linear":columns.append(relative)
 columns.extend([np.sin(omega*relative),np.cos(omega*relative)])
 design=np.column_stack(columns)
 coef=np.linalg.lstsq(design,y,rcond=None)[0];fitted=design@coef
 # 基线模型（去趋势、无周期项）的SSE，作为解释比例归一参照
 base_cols=[np.ones(len(t))]+([relative] if detrend=="linear" else [])
 base_design=np.column_stack(base_cols)
 base_fit=base_design@np.linalg.lstsq(base_design,y,rcond=None)[0]
 sse0=float(np.sum((y-base_fit)**2));sse=float(np.sum((y-fitted)**2))
 power=float(np.clip((sse0-sse)/sse0,0,1)) if sse0>0 else 0.0
 a,b=coef[-2],coef[-1]
 return power,float(np.hypot(a,b)),float(np.arctan2(b,a)),fitted,sse
def compare(points_by_window,detrend,min_frequency,max_frequency,frequency_points):
 # points_by_window: [(window_id, link_id, points[ {time_minutes,jitter_ms} ...]), ...]
 if len(points_by_window)<MIN_LINKS:
  return {"status":"insufficient_samples","conclusion":"参与链路少于2条，无法做跨链路周期对照","reasons":["多链路对照至少需要2条链路"],"links":[],"joint_spectrum":None,"shared_frequency":None,"phase_differences":[]}
 links=[]
 overlap_start=max(min(p["time_minutes"] for p in pts) for _,_,pts in points_by_window)
 overlap_end=min(max(p["time_minutes"] for p in pts) for _,_,pts in points_by_window)
 for window_id,link_id,raw in points_by_window:
  ordered=sorted(raw,key=lambda p:p["time_minutes"])
  t=np.array([p["time_minutes"] for p in ordered],dtype=float)
  y=np.array([p["jitter_ms"] for p in ordered],dtype=float)
  if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
   raise ValueError("链路 %s 存在非有限时间或抖动值"%link_id)
  if np.any(np.diff(t)<=0):raise ValueError("链路 %s 时间戳重复或非递增，不静默去重"%link_id)
  mask=(t>=overlap_start)&(t<=overlap_end)
  to,yo=t[mask],y[mask]
  links.append({"window_id":window_id,"link_id":link_id,"t":to,"y":yo,
   "window_start":float(t[0]),"window_end":float(t[-1]),
   "overlap_n":int(mask.sum()),"rejected":mask.sum()<MIN_POINTS})
 if overlap_end<=overlap_start:
  return {"status":"no_overlap","conclusion":"参与窗口没有共同覆盖时段，无法联合寻找共享频率","reasons":["各窗口时间范围互不重叠；不做外推、不补点"],"links":[{"window_id":l["window_id"],"link_id":l["link_id"],"overlap_point_count":l["overlap_n"]} for l in links],"joint_spectrum":None,"shared_frequency":None,"phase_differences":[]}
 span=float(overlap_end-overlap_start);t0=float(overlap_start)
 grid=np.linspace(min_frequency,max_frequency,frequency_points)
 joint_power=[];per_link_power=[[] for _ in links];weights=[]
 prepared=[]
 for l in links:
  residual,_offset,_slope=_detrend(l["t"],l["y"],detrend,t0)
  baseline=float(np.sum((residual-np.mean(residual))**2))
  constant=baseline<=1e-20*max(1,float(np.mean(l["y"]**2)))
  # 频率搜索与最终拟合都在原始 y 上用含趋势完整模型；residual 仅用于常量检测与权重
  prepared.append((l,baseline,constant))
  weights.append(baseline)
 if all(p[2] for p in prepared):
  return {"status":"insufficient_evidence","conclusion":"共同覆盖内全部链路去趋势后为常量，没有可对照的周期波动","reasons":["常量残差不输出共享周期或同步结论"],"links":[{"window_id":l["window_id"],"link_id":l["link_id"],"overlap_point_count":l["overlap_n"]} for l,_b,_k in prepared],"joint_spectrum":None,"shared_frequency":None,"phase_differences":[]}
 weight_sum=float(np.sum(weights)) or 1.0
 def fit_row(f):
  row=[];sse_sum=0.0
  for idx,(l,baseline,constant) in enumerate(prepared):
   if constant or l["rejected"]:
    row.append(0.0);continue
   power,_,_,_fitted,sse=_link_power(l["t"],l["y"],detrend,float(f),t0)
   row.append(power);sse_sum+=sse
  return row,sse_sum
 def scan(f):
  row,sse_sum=fit_row(f)
  acc=sum(prepared[i][1]*row[i] for i in range(len(prepared)))
  return float(np.clip(acc/weight_sum,0,1)),row
 for f in grid:
  jp,row=scan(f);joint_power.append(jp)
  for idx,v in enumerate(row):per_link_power[idx].append(v)
 joint_spectrum={"frequencies":[float(x) for x in grid],"power":joint_power,
  "per_link_power":[[float(v) for v in seq] for seq in per_link_power],
  "units":"联合解释方差比例（按各链路去趋势基线SSE加权，无量纲）",
  "normalization":"Σ_k SSE0_k·P_k(f)/Σ_k SSE0_k；每条链路在原始观测上按真实采样时刻拟合常数(+线性)+sin+cos，缺点不补点",
  "search_strategy":"共同覆盖时段内显式等频率网格，并对每个联合局部峰在±一个网格间距内201点细化；设计矩阵仅依赖(t−共同原点)，对时间整体平移不变；不规则采样无统一Nyquist",
  "coarse_grid_points":frequency_points}
 # 粗网格局部最大峰（复用与单链路一致的 1/跨度 最小分离规则）
 from src.services.peaks import top_peaks
 coarse_peaks=top_peaks(grid,np.array(joint_power),5,1/span)
 # 细化括号以峰所在网格索引的相邻网格线 [i-1,i+1] 界定，仅由绝对频率轴决定，
 # 与数据时间原点无关，故细化子网格和结果对时间整体平移严格不变。
 REFINE_POINTS=201
 def quadratic_vertex(fl,fm,fr,sl,sm,sr):
  # 三点逆二次插值求 SSE 极小；顶点落在 (fl,fr) 内才采用，否则回退网格最优点
  denom=(sl-sm)*(fm-fr)-(sm-sr)*(fm-fl)
  if abs(denom)<1e-300:return fm
  vertex=fm+0.5*((fl-fm)**2*(sm-sr)-(fm-fr)**2*(sl-sm))/denom
  return vertex if fl<vertex<fr else fm
 refined_peaks=[]
 for peak in coarse_peaks:
  gi=int(np.argmin(np.abs(grid-peak["frequency_per_minute"])))
  lo_idx=max(0,gi-1);hi_idx=min(len(grid)-1,gi+1)
  lo,hi=float(grid[lo_idx]),float(grid[hi_idx])
  sub=np.linspace(lo,hi,REFINE_POINTS)
  sse_list=[]
  for f in sub:
   row,sse=fit_row(float(f));sse_list.append(sse)
  mi=int(np.argmin(sse_list));best_f=float(sub[mi])
  if 0<mi<len(sub)-1:
   qf=quadratic_vertex(float(sub[mi-1]),best_f,float(sub[mi+1]),
    sse_list[mi-1],sse_list[mi],sse_list[mi+1])
   if math.isfinite(qf):best_f=qf
  best_row,best_sse=fit_row(best_f)
  jp,_=scan(best_f)
  refined_peaks.append({"frequency_per_minute":float(best_f),"period_minutes":1/float(best_f),
   "power":float(jp),"coarse_power":float(peak["power"]),"per_link_power":best_row})
 joint_peaks=refined_peaks
 joint_spectrum["refined_peaks"]=[{"frequency_per_minute":p["frequency_per_minute"],"period_minutes":p["period_minutes"],"power":p["power"]} for p in refined_peaks]
 link_payload=[];valid_idx=[]
 for idx,(l,baseline,constant) in enumerate(prepared):
  payload={"window_id":l["window_id"],"link_id":l["link_id"],
   "window_start_minutes":l["window_start"],"window_end_minutes":l["window_end"],
   "overlap_start_minutes":float(overlap_start),"overlap_end_minutes":float(overlap_end),
   "overlap_span_minutes":span,"overlap_point_count":l["overlap_n"],"n":l["overlap_n"]}
  if l["rejected"]:
   payload.update({"usable":False,"reason":"共同覆盖内不足%d点，不参与共享频率判定"%MIN_POINTS})
  elif constant:
   payload.update({"usable":False,"reason":"去趋势后为常量，没有可分析周期"})
  else:
   payload["usable"]=True;valid_idx.append(idx)
  link_payload.append(payload)
 if len(valid_idx)<MIN_LINKS:
  return {"status":"insufficient_samples","conclusion":"共同覆盖内有效链路不足2条，不能给出跨链路同步结论",
   "reasons":["至少需要2条链路在共同覆盖内各有≥%d个真实采样点"%MIN_POINTS],
   "links":link_payload,"joint_spectrum":joint_spectrum,"shared_frequency":None,"phase_differences":[]}
 # 在细化后的联合峰上逐条核对每链路证据，选出全部有效链路都达标的最高联合功率峰
 chosen=None;reasons=[]
 for peak in joint_peaks:
  f=peak["frequency_per_minute"]
  row=[];ok=True
  for idx in valid_idx:
   p=peak["per_link_power"][idx]
   hit=p>=PER_LINK_POWER_MIN
   ok=ok and hit
   row.append({"link_id":prepared[idx][0]["link_id"],"power":p,"passes":hit})
  if ok and peak["power"]>=SHARED_POWER_MIN:
   chosen=(f,row,peak["power"]);break
  reasons.append("候选周期 %.3f 分钟（%.6f /min）：联合解释比例 %.4f，未全部达标链路 %s"%(
   1/f,f,peak["power"],"、".join(r["link_id"] for r in row if not r["passes"]) or "联合功率低于阈值"))
 if chosen is None:
  return {"status":"insufficient_evidence",
   "conclusion":"共同覆盖内没有足够证据支持共享周期，不给出跨链路同步结论",
   "reasons":reasons or ["联合谱未出现满足每链路解释比例≥%.2f且联合≥%.2f的共享峰"%(PER_LINK_POWER_MIN,SHARED_POWER_MIN)],
   "joint_peaks":joint_peaks,"links":link_payload,"joint_spectrum":joint_spectrum,
   "shared_frequency":None,"phase_differences":[]}
 f,evidence,joint_p=chosen
 estimated=[]
 for idx,(l,baseline,constant) in enumerate(prepared):
  payload=next(x for x in link_payload if x["link_id"]==l["link_id"])
  if idx not in valid_idx:
   estimated.append(payload);continue
  # 在原始观测上以共享频率联合估计趋势/振幅/相位；统一原点 t0=共同覆盖起点（绝对时间）
  t=l["t"];relative=t-t0;omega=2*np.pi*f
  columns=[np.ones(len(t))]
  if detrend=="linear":columns.append(relative)
  columns.extend([np.sin(omega*relative),np.cos(omega*relative)])
  design=np.column_stack(columns)
  coef,_,rank,_=np.linalg.lstsq(design,l["y"],rcond=None)
  if rank<len(columns):raise ValueError("链路 %s 对照拟合设计矩阵退化"%l["link_id"])
  fitted=design@coef
  # 列布局：[常数, (线性斜率), sin, cos]；sin/cos 恒为最后两列
  a,b=coef[-2],coef[-1]
  slope=float(coef[1]) if detrend=="linear" else 0.0
  amplitude=float(np.hypot(a,b));phase=float(np.arctan2(b,a))
  sse=float(np.sum((l["y"]-fitted)**2));tot=float(np.sum((l["y"]-np.mean(l["y"]))**2))
  # 残差只在真实采样点上给出，缺采样位置不补点
  obs=[{"time_minutes":float(tt),"jitter_ms":float(vv),"fitted_ms":float(ff),"residual_ms":float(vv-ff)}
       for tt,vv,ff in zip(t,l["y"],fitted)]
  payload.update({"usable":True,
   "frequency_per_minute":float(f),"period_minutes":1/float(f),
   "amplitude_ms":amplitude,"phase_radians":phase,
   "offset_ms":float(coef[0]),"slope_ms_per_minute":slope,
   "rmse_ms":float(np.sqrt(sse/len(t))),
   "r_squared":(1-sse/tot) if tot>0 else None,
   "ls_power":next(e["power"] for e in evidence if e["link_id"]==l["link_id"]),"observations":obs})
  estimated.append(payload)
 # 两两相位差：以共同绝对原点 t0 估计的相位直接相减，对时间整体平移不变
 phase_differences=[]
 usable=[p for p in estimated if p.get("usable")]
 for i in range(len(usable)):
  for j in range(i+1,len(usable)):
   d=float(usable[j]["phase_radians"]-usable[i]["phase_radians"])
   wrapped=float((d+np.pi)%(2*np.pi)-np.pi)
   phase_differences.append({"link_a":usable[i]["link_id"],"link_b":usable[j]["link_id"],
    "phase_difference_radians":wrapped,
    "time_lag_minutes":float(wrapped/(2*np.pi*f)),
    "amplitude_ratio":float(usable[j]["amplitude_ms"]/usable[i]["amplitude_ms"]) if usable[i]["amplitude_ms"]>0 else None})
 shared={"frequency_per_minute":float(f),"period_minutes":1/float(f),
  "joint_power":float(joint_p),
  "per_link_evidence":evidence,
  "phase_origin_minutes":t0,
  "phase_convention":"A*sin(2*pi*f*(t-t0)+phi)，t0为共同覆盖起点（统一绝对时间原点）；相位差对窗口错开与时间整体平移不变",
  "criteria":{"per_link_power_min":PER_LINK_POWER_MIN,"joint_power_min":SHARED_POWER_MIN,
   "min_links":MIN_LINKS,"min_points_per_link":MIN_POINTS}}
 return {"status":"completed",
  "conclusion":"共同覆盖内找到满足证据阈值的共享频率，可比较各链路趋势/振幅与相位差；相位差仅描述该共享频率上的时间关系，不构成故障因果或完全同步的证明",
  "reasons":[],"links":estimated,"joint_spectrum":joint_spectrum,"joint_peaks":joint_peaks,
  "shared_frequency":shared,"phase_differences":phase_differences,
  "overlap_start_minutes":float(overlap_start),"overlap_end_minutes":float(overlap_end),
  "overlap_span_minutes":span,"detrend":detrend,
  "frequency_min":float(min_frequency),"frequency_max":float(max_frequency),
  "frequency_points":int(frequency_points),
  "assumptions":[
   "仅在参与窗口的共同覆盖时段内联合搜索；各链路保留自己的真实采样时刻，缺采样不补0、不插值、不重采样。",
   "联合谱按各链路去趋势残差平方和加权浮动均值LS；共享频率需每条有效链路解释比例≥%.2f且联合≥%.2f。"%(PER_LINK_POWER_MIN,SHARED_POWER_MIN),
   "趋势（截距/斜率）、振幅与相位在原始观测上以共享频率联合最小二乘估计；相位原点统一为共同覆盖起点t0。",
   "窗口边界错开或所有时间整体平移时，共同原点随之平移，链路间相位差保持一致；单链路以各自窗口首点计的相位不可直接比较。",
   "证据不足、无共同覆盖或样本不足时只报告状态与原因，不给同步结论；相位差不证明网络故障因果，也不保证其它频率同步。"]}
