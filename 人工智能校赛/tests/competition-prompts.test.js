import test from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {createServer} from '../server.js';
import {competitionPrompts} from '../engine/prompts.js';
import {allowAnalysis,finishAnalysis,sessionValid} from '../engine/limits.js';

test('three jury prompts remain reproducible and role bound',()=>{
 assert.deepEqual(competitionPrompts.map(x=>x.id),['P1','P2','P3']);
 assert.deepEqual(competitionPrompts.map(x=>x.role),['claimant','respondent','neutral']);
});
test('budget, concurrency and expiry are enforced',()=>{
 const session={id:'s',createdAt:new Date().toISOString(),analysis_count_total:0,inflight:false};
 const sessions=new Map([['s',session]]);
 assert.equal(sessionValid(sessions,'s'),true);
 assert.equal(allowAnalysis(session).ok,true);
 assert.equal(allowAnalysis(session).reason,'analysis_in_progress');
 finishAnalysis(session);
 session.analysis_count_total=12;
 assert.equal(allowAnalysis(session).reason,'session_budget_exhausted');
 assert.equal(sessionValid(new Map([['s',{...session,createdAt:new Date(0).toISOString()}]]),'s'),false);
});
test('jury API executes a registered prompt and rejects invalid prompt ID',async()=>{
 const server=createServer().listen(0,'127.0.0.1');await once(server,'listening');
 const root='http://127.0.0.1:'+server.address().port;
 try{
  const prompts=await(await fetch(root+'/api/prompts')).json();
  assert.equal(prompts.prompts.length,3);
  const sess=await(await fetch(root+'/api/session',{method:'POST'})).json();
  const run=await fetch(root+'/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sess.id,prompt_id:'P1'})});
  assert.equal(run.status,200);
  const result=await run.json();assert.equal(result.role,'claimant');
  const invalid=await fetch(root+'/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sess.id,prompt_id:'P100'})});
  assert.equal(invalid.status,400);
 }finally{await new Promise(resolve=>server.close(resolve))}
});
