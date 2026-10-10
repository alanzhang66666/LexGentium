// Per-process safeguards for a public demonstration. Not multi-instance authentication.
const MAX_AGE_MS=30*60*1000;
const WINDOW_MS=60*1000;
const MAX_REQUESTS=6;
const counts=new Map();
let globalCount=0;
let globalDay='';
function dayKey(now){return new Date(now).toISOString().slice(0,10)}
export function resetGlobalBudgetForTests(){globalCount=0;globalDay='';counts.clear()}
export function globalBudgetStatus(now=Date.now()){
 const day=dayKey(now);if(globalDay!==day){globalDay=day;globalCount=0}
 const budget=Number.parseInt(process.env.LLM_MAX_DAILY_REQUESTS||'60',10);
 const max=Number.isFinite(budget)&&budget>=0?budget:60;
 return {used:globalCount,max,remaining:Math.max(0,max-globalCount)};
}
export function sessionValid(sessions,id,now=Date.now()){
 const session=sessions.get(id);
 if(!session)return false;
 if(now-Date.parse(session.createdAt)>MAX_AGE_MS){sessions.delete(id);return false}
 return true;
}
export function allowAnalysis(session,now=Date.now()){
 const budget=globalBudgetStatus(now);
 if(budget.remaining<=0)return {ok:false,status:429,reason:'global_budget_exhausted'};
 if(session.analysis_count_total>=12)return {ok:false,status:429,reason:'session_budget_exhausted'};
 if(session.inflight)return {ok:false,status:429,reason:'analysis_in_progress'};
 const times=(counts.get(session.id)||[]).filter(time=>now-time<WINDOW_MS);
 if(times.length>=MAX_REQUESTS)return {ok:false,status:429,reason:'rate_limited'};
 times.push(now);counts.set(session.id,times);
 globalCount++;
 session.analysis_count_total++;
 session.inflight=true;
 return {ok:true};
}
export function finishAnalysis(session){session.inflight=false}
