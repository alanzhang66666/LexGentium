// Per-process safeguards for a public demonstration. Not multi-instance authentication.
const MAX_AGE_MS=30*60*1000;
const WINDOW_MS=60*1000;
const MAX_REQUESTS=6;
const counts=new Map();
export function sessionValid(sessions,id,now=Date.now()){
 const session=sessions.get(id);
 if(!session)return false;
 if(now-Date.parse(session.createdAt)>MAX_AGE_MS){sessions.delete(id);return false}
 return true;
}
export function allowAnalysis(session,now=Date.now()){
 if(session.analysis_count_total>=12)return {ok:false,status:429,reason:'session_budget_exhausted'};
 if(session.inflight)return {ok:false,status:429,reason:'analysis_in_progress'};
 const times=(counts.get(session.id)||[]).filter(time=>now-time<WINDOW_MS);
 if(times.length>=MAX_REQUESTS)return {ok:false,status:429,reason:'rate_limited'};
 times.push(now);counts.set(session.id,times);
 session.analysis_count_total++;
 session.inflight=true;
 return {ok:true};
}
export function finishAnalysis(session){session.inflight=false}
