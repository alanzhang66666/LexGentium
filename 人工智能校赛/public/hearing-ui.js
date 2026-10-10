// Lightweight 2.5D SVG hearing visualization for the school competition edition.
// Events are retrieved from the same server session; this is synthetic replay, not a live hearing.
const labels={arbitrator:'首席仲裁员',claimant:'申请人代理',respondent:'被申请人代理'};
const esc=t=>String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let events=[],index=0,interval=null,currentSession=null;
function stop(){if(interval){clearInterval(interval);interval=null}}
function seat(role,x,y){
 const active=events[index]?.role===role;
 return '<g class="hearing-seat '+(active?'speaking':'')+'" transform="translate('+x+' '+y+')">'+
 '<ellipse cx="0" cy="21" rx="73" ry="18" fill="#091d31" opacity=".34"/>'+
 '<rect x="-67" y="-20" width="134" height="69" rx="10" fill="'+(active?'#7b663d':'#365674')+'" stroke="'+(active?'#f6cf7b':'#8fa8bd')+'" stroke-width="'+(active?4:1)+'"/>'+
 '<rect x="-49" y="-58" width="98" height="42" rx="15" fill="#6689a7"/>'+
 '<circle cx="0" cy="-63" r="18" fill="#ebc9a5"/>'+
 '<text x="0" y="12" text-anchor="middle" font-size="13" font-weight="600" fill="white">'+esc(labels[role])+'</text>'+
 (active?'<circle cx="54" cy="-31" r="8" fill="#f5ce76"/>':'')+'</g>';
}
function scene(){
 return '<svg class="hearing-scene" viewBox="0 0 760 410" role="img" aria-label="国际商事仲裁庭座席示意图，金色轮廓表示当前发言人">'+
 '<defs><linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#47617b"/><stop offset="1" stop-color="#192e46"/></linearGradient></defs>'+
 '<rect width="760" height="410" rx="20" fill="#152c43"/>'+
 '<path d="M0 170 L380 75 L760 170 L760 410 L0 410Z" fill="url(#floor)"/>'+
 '<path d="M130 166 L630 166 L742 410 L18 410Z" fill="#6b4d38" opacity=".25"/>'+
 '<path d="M160 154 L600 154 L650 207 L110 207Z" fill="#78553d" stroke="#ba9470" stroke-width="4"/>'+
 '<text x="380" y="38" fill="#e2ecf3" font-size="20" text-anchor="middle" letter-spacing="4">国际商事仲裁庭 · 程序模拟</text>'+
 seat('arbitrator',380,163)+seat('claimant',205,299)+seat('respondent',555,299)+
 '</svg>';
}
function draw(){
 const root=document.getElementById('hearing-visual');
 if(!root||!events.length)return;
 const ev=events[index];
 root.innerHTML=scene()+
 '<div class="hearing-subtitle"><span class="tag">预置听证记录 · '+(index+1)+' / '+events.length+'</span>'+
 '<h3>'+esc(labels[ev.role]||ev.role)+'</h3><p>'+esc(ev.text)+'</p>'+
 '<p class="muted">来源标识：'+(ev.source_ids||[]).map(esc).join(' · ')+'</p></div>'+
 '<div class="hearing-controls"><button id="hearing-back" type="button">上一条</button><button id="hearing-play" type="button">'+(interval?'暂停':'播放')+'</button><button id="hearing-next" type="button">下一条</button></div>'+
 '<ol class="hearing-timeline">'+events.map((e,i)=>'<li><button class="'+(i===index?'selected':'')+'" type="button" data-step="'+i+'">'+(i+1)+'. '+esc(labels[e.role]||e.role)+'</button></li>').join('')+'</ol>';
 document.getElementById('hearing-back').onclick=()=>{stop();index=Math.max(0,index-1);draw()};
 document.getElementById('hearing-next').onclick=()=>{stop();index=Math.min(events.length-1,index+1);draw()};
 document.getElementById('hearing-play').onclick=()=>{
  if(interval){stop();draw();return}
  interval=setInterval(()=>{if(index>=events.length-1){stop();draw()}else{index++;draw()}},2600);
  draw();
 };
 root.querySelectorAll('[data-step]').forEach(btn=>btn.onclick=()=>{stop();index=Number(btn.dataset.step);draw()});
}
export async function mountHearing(sessionId){
 stop();events=[];index=0;currentSession=sessionId;
 const root=document.getElementById('hearing-visual');if(!root)return;
 if(!sessionId){root.textContent='请先从案件接入页面启动示范会话。';return}
 root.textContent='正在读取本场听证记录…';
 try{
  const response=await fetch('/api/hearing?session_id='+encodeURIComponent(sessionId));
  if(!response.ok)throw new Error('会话不存在或已经失效');
  const payload=await response.json();
  if(currentSession!==sessionId||!document.getElementById('hearing-visual'))return;
  if(payload.mode!=='synthetic_replay'||payload.session_id!==sessionId||!Array.isArray(payload.events))throw new Error('听证数据格式不匹配');
  events=payload.events.filter(e=>typeof e.text==='string'&&Object.hasOwn(labels,e.role));
  if(!events.length)throw new Error('本场没有可用听证事件');
  draw();
 }catch(err){if(document.getElementById('hearing-visual'))root.textContent=err.message}
}
export function unmountHearing(){stop();currentSession=null}
