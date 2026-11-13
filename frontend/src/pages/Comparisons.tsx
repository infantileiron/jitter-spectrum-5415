import {useState} from 'react';
import type {Workspace} from '../stores/workspace';
import {PageHeading} from '../components/common/PageHeading';
import {Notice} from '../components/common/Notice';
import {Empty} from '../components/common/Empty';
import {Status} from '../components/common/Status';
import {JointSpectrumPlot} from '../components/JointSpectrumPlot';
import {ComparisonTrace} from '../components/ComparisonTrace';
import {createStudy as createComparisonStudy,createRun} from '../api/comparisons';
import {useAsync} from '../hooks/useAsync';
import {DETRENDS} from '../constants/enums';
import {number,date} from '../utils/format';
export function Comparisons({data,canWrite,refresh}:{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}){
 const [name,setName]=useState(''),[windowIds,setWindowIds]=useState<string[]>([]),[detrend,setDetrend]=useState('linear'),
  [min,setMin]=useState(.005),[max,setMax]=useState(.1),[count,setCount]=useState(1400),[selected,setSelected]=useState('');
 const task=useAsync();
 const run=data.comparisonRuns.find(r=>r.id===selected)||data.comparisonRuns[0];
 const studyName=(id:string)=>data.comparisonStudies.find(s=>s.id===id)?.name||'—';
 function toggle(id:string){setWindowIds(prev=>prev.includes(id)?prev.filter(x=>x!==id):[...prev,id]);}
 const result=run?.result;
 const usableLinks=result?.links.filter(l=>l.usable)||[];
 return <><PageHeading label="07 / MULTI-LINK CROSS-CHECK" title="同一时钟原点，才能比较相位。">各链路在共同覆盖内按真实采样时刻联合寻找共享频率，缺采样不补点。<br/>相位以共同覆盖起点为统一原点；证据不足时只给原因，不给同步结论。</PageHeading>
 {canWrite&&<section className="paper"><h2>新建多链路周期对照</h2>
  <form className="study-form" onSubmit={e=>{e.preventDefault();task.execute(async()=>{await createComparisonStudy({name,window_ids:windowIds,detrend,min_frequency:min,max_frequency:max,frequency_points:count});setName('');setWindowIds([]);await refresh();});}}>
   <label>对照名称<input aria-label="对照名称" minLength={2} required value={name} onChange={e=>setName(e.target.value)}/></label>
   <label>去趋势<select aria-label="去趋势方式" value={detrend} onChange={e=>setDetrend(e.target.value)}><option value="mean">去均值</option><option value="linear">去线性趋势</option></select></label>
   <label>LS网格点数<input type="number" min={32} max={4000} value={count} onChange={e=>setCount(+e.target.value)}/></label>
   <label>最低频率 / 每分钟<input aria-label="最低频率" type="number" min=".000001" step="any" value={min} onChange={e=>setMin(+e.target.value)}/></label>
   <label>最高频率 / 每分钟<input aria-label="最高频率" type="number" min=".000001" step="any" value={max} onChange={e=>setMax(+e.target.value)}/></label>
   <div className="coverage-note">已选 {windowIds.length} 个窗口（需2—12个、来自不同链路且有共同覆盖）</div>
   <div className="window-picker wide">
    {data.windows.map(w=><label key={w.id} className={'chip'+(windowIds.includes(w.id)?' on':'')}><input type="checkbox" checked={windowIds.includes(w.id)} onChange={()=>toggle(w.id)}/><span>{w.link_id}</span><small>{w.name}</small></label>)}
   </div>
   {task.error&&<div className="wide"><Notice error>{task.error}</Notice></div>}
   <button disabled={task.busy||windowIds.length<2}>保存并准备对照</button>
  </form></section>}
 <section className="paper">
  <div className="section-heading"><h2>对照研究与运行</h2><span>{DETRENDS[detrend]}</span></div>
  {data.comparisonStudies.length===0?<Empty>请先选择至少2个不同链路、有共同覆盖的窗口建立对照。</Empty>:
   <div className="table-scroll"><table><thead><tr><th>对照研究</th><th>窗口数</th><th>频率范围 /min</th><th>操作</th></tr></thead><tbody>
    {data.comparisonStudies.map(s=><tr key={s.id}><td><b>{s.name}</b><small>{DETRENDS[s.detrend]} · {date(s.created_at)}</small></td><td>{s.window_ids.length}</td><td>{number(s.min_frequency,4)}—{number(s.max_frequency,4)}</td>
     <td>{canWrite&&<button className="secondary" disabled={task.busy} onClick={()=>task.execute(async()=>{const r=await createRun({study_id:s.id});setSelected(r.id);await refresh();})}>运行联合对照 →</button>}</td></tr>)}
   </tbody></table></div>}
 </section>
 <div className="run-selector"><label>对照运行记录<select aria-label="选择对照运行" value={run?.id||''} onChange={e=>setSelected(e.target.value)}>{data.comparisonRuns.map(r=><option key={r.id} value={r.id}>{studyName(r.study_id)} · {r.created_at.slice(11,19)}</option>)}</select></label>{run&&<Status value={run.status}/>}</div>
 {!run?<Empty>尚无对照运行，建立对照研究后运行独立worker。</Empty>:
  run.status!=='completed'?<Notice error={run.status==='failed'}>{run.status==='failed'?run.error:'后台正在联合计算共享频率与相位差，页面会自动刷新。'}</Notice>:
  <ComparisonResult result={result!}/>}
 </>;
}
function ComparisonResult({result}:{result:import('../types/domain').ComparisonResult}){
 const usable=result.links.filter(l=>l.usable);
 return <>
  <section className="paper">
   <div className="section-heading"><h2>对照结论</h2><span className={'status '+(result.shared_frequency?'completed':'needs_attention')}>{result.shared_frequency?'找到共享频率':'证据不足 / 无结论'}</span></div>
   <p>{result.conclusion}</p>
   {result.reasons.length>0&&<ul className="reason-list">{result.reasons.map((r,i)=><li key={i}>{r}</li>)}</ul>}
   {result.shared_frequency&&<div className="result-metrics">
    <div><small>共享周期 / 分钟</small><b>{number(result.shared_frequency.period_minutes,3)}</b></div>
    <div><small>共享频率 / 每分钟</small><b>{number(result.shared_frequency.frequency_per_minute,6)}</b></div>
    <div><small>联合解释比例</small><b>{number(result.shared_frequency.joint_power,4)}</b></div>
    <div><small>统一相位原点 / 分钟</small><b>{number(result.shared_frequency.phase_origin_minutes,2)}</b></div>
   </div>}
   {result.overlap_start_minutes!=null&&<p className="caption">共同覆盖 {number(result.overlap_start_minutes,2)}—{number(result.overlap_end_minutes,2)} 分钟，跨度 {number(result.overlap_span_minutes,2)} 分钟；各链路只用自己的真实采样点，缺采样不补。</p>}
  </section>
  {result.joint_spectrum&&<section className="paper"><div className="section-heading"><h2>联合浮动均值LS周期谱</h2><span>{result.joint_spectrum.units}</span></div>
   <JointSpectrumPlot spectrum={result.joint_spectrum} links={result.links}/>
   <p className="caption">{result.joint_spectrum.normalization}。{result.joint_spectrum.search_strategy}。</p></section>}
  {result.shared_frequency&&<section className="paper"><h2>各链路共享频率拟合（趋势 / 振幅 / 相位）</h2>
   <div className="table-scroll"><table><thead><tr><th>链路</th><th>共同覆盖点数</th><th>截距 / ms</th><th>斜率 / ms·min⁻¹</th><th>振幅 / ms</th><th>相位 / rad</th><th>LS解释比例</th><th>RMSE / ms</th><th>R²</th></tr></thead><tbody>
    {usable.map(l=><tr key={l.link_id}><td><b>{l.link_id}</b></td><td>{l.overlap_point_count}</td><td>{number(l.offset_ms,4)}</td><td>{number(l.slope_ms_per_minute,6)}</td><td>{number(l.amplitude_ms,4)}</td><td>{number(l.phase_radians,4)}</td><td>{number(l.ls_power,4)}</td><td>{number(l.rmse_ms,4)}</td><td>{number(l.r_squared,4)}</td></tr>)}
   </tbody></table></div>
   <p className="caption">{result.shared_frequency.phase_convention}。每链路阈值 {result.shared_frequency.criteria.per_link_power_min}，联合阈值 {result.shared_frequency.criteria.joint_power_min}。</p></section>}
  {usable.length>=2&&result.shared_frequency&&<section className="paper"><h2>两两相位差与时滞</h2>
   <div className="table-scroll"><table><thead><tr><th>链路 A</th><th>链路 B</th><th>相位差 / rad（−π,π）</th><th>等效时滞 / 分钟</th><th>振幅比 B/A</th></tr></thead><tbody>
    {result.phase_differences.map(d=><tr key={d.link_a+d.link_b}><td>{d.link_a}</td><td>{d.link_b}</td><td>{number(d.phase_difference_radians,4)}</td><td>{number(d.time_lag_minutes,3)}</td><td>{d.amplitude_ratio==null?'不适用':number(d.amplitude_ratio,4)}</td></tr>)}
   </tbody></table></div></section>}
  {usable.some(l=>l.observations?.length)&&<section className="paper"><h2>共同覆盖内观测与共享频率拟合</h2><ComparisonTrace links={usable} mode="fit"/></section>}
  {usable.some(l=>l.observations?.length)&&<section className="paper"><h2>各链路拟合残差（仅真实采样点）</h2><ComparisonTrace links={usable} mode="residual"/></section>}
  {result.links.some(l=>l.usable===false)&&<section className="paper"><h2>未参与判定的链路</h2>
   <div className="table-scroll"><table><thead><tr><th>链路</th><th>共同覆盖点数</th><th>原因</th></tr></thead><tbody>
    {result.links.filter(l=>l.usable===false).map(l=><tr key={l.link_id}><td>{l.link_id}</td><td>{l.overlap_point_count}</td><td>{l.reason}</td></tr>)}
   </tbody></table></div></section>}
  {result.assumptions&&<aside className="assumptions"><h2>解释边界</h2>{result.assumptions.map((a,i)=><p key={a}><b>0{i+1}</b>{a}</p>)}{result.checksum&&<small>窗口观测校验码 {result.checksum.slice(0,24)}</small>}</aside>}
 </>;
}
