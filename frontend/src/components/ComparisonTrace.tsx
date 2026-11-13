import type {ComparisonLink} from '../types/domain';
// 多链路在共同覆盖时段内的真实点与共享频率拟合/残差；只画真实采样点，缺采样位置留空不补
const PALETTE=['#3b4a8f','#b07b3c','#3f7a5b','#8a4a6d','#5a6b8c','#9a6a2f','#467a7a','#7a4a8f'];
export function ComparisonTrace({links,mode}:{links:ComparisonLink[];mode:'fit'|'residual'}){
 const usable=links.filter(l=>l.usable&&l.observations&&l.observations.length);
 if(!usable.length)return <p>暂无可绘制的有效链路观测。</p>;
 const t0=Math.min(...usable.map(l=>Math.min(...l.observations!.map(o=>o.time_minutes))));
 const t1=Math.max(...usable.map(l=>Math.max(...l.observations!.map(o=>o.time_minutes))));
 const vals:number[]=[];
 usable.forEach(l=>l.observations!.forEach(o=>vals.push(mode==='residual'?o.residual_ms:o.jitter_ms)));
 if(mode==='fit')usable.forEach(l=>l.observations!.forEach(o=>vals.push(o.fitted_ms)));
 const low=Math.min(...vals),high=Math.max(...vals),range=Math.max(1e-8,high-low),T=Math.max(1e-8,t1-t0);
 const x=(t:number)=>53+(t-t0)/T*690,y=(v:number)=>194-(v-low)/range*155;
 return <svg className="signal-trace" viewBox="0 0 780 245" aria-label={mode==='residual'?'多链路共享频率残差':'多链路观测与共享频率拟合'}>
  <line x1="53" x2="743" y1="194" y2="194"/>
  {[0,.5,1].map(v=><g key={v}><line className="grid" x1="53" x2="743" y1={194-v*155} y2={194-v*155}/><text x="4" y={198-v*155}>{(low+v*range).toFixed(2)}</text></g>)}
  {usable.map((l,i)=>{const c=PALETTE[i%PALETTE.length];const obs=l.observations!;
   return <g key={l.link_id}>
    <polyline className="observed" points={obs.map(o=>`${x(o.time_minutes)},${y(mode==='residual'?o.residual_ms:o.jitter_ms)}`).join(' ')} fill="none" stroke={c} strokeWidth="1.3"/>
    {mode==='fit'&&<polyline className="fitted" points={obs.map(o=>`${x(o.time_minutes)},${y(o.fitted_ms)}`).join(' ')} fill="none" stroke={c} strokeWidth="1.2" strokeDasharray="5 3" opacity=".85"/>}
    <text x={55+i*120} y="17" fontSize="10" fill={c}>{l.link_id} · {obs.length}点</text>
   </g>;})}
  <text x="53" y="222">{t0.toFixed(1)} min</text><text x="650" y="222">{t1.toFixed(1)} min</text>
 </svg>;
}
