import test from 'node:test';
import assert from 'node:assert/strict';
import {allowAnalysis,finishAnalysis,globalBudgetStatus,resetGlobalBudgetForTests} from '../engine/limits.js';
import {analyze} from '../engine/llm.js';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/golden-case.json',import.meta.url),'utf8'));
test('daily global budget blocks excess requests across sessions',()=>{
 const prior=process.env.LLM_MAX_DAILY_REQUESTS;
 try{
  process.env.LLM_MAX_DAILY_REQUESTS='2';resetGlobalBudgetForTests();
  for(let i=0;i<2;i++){
   const session={id:'unique'+i,analysis_count_total:0,inflight:false};
   assert.equal(allowAnalysis(session).ok,true);finishAnalysis(session);
  }
  const third={id:'third',analysis_count_total:0,inflight:false};
  assert.equal(allowAnalysis(third).reason,'global_budget_exhausted');
  assert.equal(globalBudgetStatus().remaining,0);
 }finally{prior===undefined?delete process.env.LLM_MAX_DAILY_REQUESTS:process.env.LLM_MAX_DAILY_REQUESTS=prior;resetGlobalBudgetForTests()}
});
test('an unapproved upstream never attempts a live model call',async()=>{
 const names=['LLM_API_KEY','LLM_MODEL','LLM_BASE_URL','LLM_ALLOWED_HOSTS'];
 const previous=names.map(n=>process.env[n]);
 try{
  process.env.LLM_API_KEY='fake';process.env.LLM_MODEL='mock';process.env.LLM_BASE_URL='https://unapproved.example/v1';
  process.env.LLM_ALLOWED_HOSTS='approved.example';
  const result=await analyze(data,'核对供应链证据',{role:'neutral'});
  assert.equal(result.mode,'structured_demo');
  assert.match(result.notice,/白名单/);
 }finally{names.forEach((n,i)=>previous[i]===undefined?delete process.env[n]:process.env[n]=previous[i])}
});
