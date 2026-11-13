import type {JointSpectrum,ComparisonLink} from '../types/domain';
// 联合LS周期谱（加权解释比例）与各链路自身解释比例，分色叠加；缺采样链路功率为0不参与
export function JointSpectrumPlot({spectrum,links}:{spectrum:JointSpectrum;links:ComparisonLink[]}){
 if(!spectrum.frequencies.length)return <p>没有可绘制的频率点。</p>;
 const f=spectrum.frequencies,p=spectrum.power,low=f[0],span=Math.max(1e-12,f[f.length-1]-low),top=Math.max(1e-12,...p)*1.08;
 const x=(v:number)=>55+(v-low)/span*670,y=(v:number)=>205-v/top*160;
 const palette=['#3b4a8f','#b07b3c','#3f7a5b','#8a4a6d','#5a6b8c','#9a6a2f','#467a7a','#7a4a8f'];
 return <svg className="spectrum-plot ls" viewBox="0 0 780 255" aria-label="多链路联合LS周期谱">
  <line x1="55" x2="725" y1="205" y2="205"/>
  {[0,.5,1].map(v=><g key={v}><line className="grid" x1="55" x2="725" y1={205-v*160} y2={205-v*160}/><text x="2" y={209-v*160}>{(top*v).toPrecision(3)}</text></g>)}
  <polyline points={f.map((v,i)=>`${x(v)},${y(p[i])}`).join(' ')} fill="none" strokeWidth="2.2"/>
  {spectrum.per_link_power.map((seq,i)=><polyline key={i} points={f.map((v,k)=>`${x(v)},${y(seq[k])}`).join(' ')} fill="none" stroke={palette[i%palette.length]} strokeWidth="1" strokeDasharray="4 4" opacity=".75"/>)}
  {(spectrum.refined_peaks||[]).slice(0,2).map((pk,i)=><g key={pk.frequency_per_minute}><circle cx={x(pk.frequency_per_minute)} cy={y(pk.power)} r="4"/><text className="peak-label" x={x(pk.frequency_per_minute)+7} y={y(pk.power)-10-i*3}>{pk.period_minutes.toFixed(1)}min</text></g>)}
  <text x="55" y="235">{low.toFixed(4)}</text><text x="640" y="235">{f[f.length-1].toFixed(4)} /min</text>
  <text x="55" y="19">{spectrum.units}</text>
  <g>{links.map((l,i)=><text key={l.link_id} x={55+i*130} y="38" fontSize="10" fill={palette[i%palette.length]}>{l.link_id}{l.usable===false?'（不参与）':''}</text>)}</g>
 </svg>;
}
