import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateArguments,demoArguments} from '../engine/arguments.js';
import {analyze} from '../engine/llm.js';
const data=JSON.parse(readFileSync(new URL('../data/golden-case.json',import.meta.url),'utf8'));
test('party argument contracts stay distinct and citations resolve',()=>{
 const a=demoArguments(data,'claimant'),b=demoArguments(data,'respondent');
 assert.notEqual(a.arguments[0].claim,b.arguments[0].claim);
 for(const x of [a,b]){assert.equal(x.verified_reference_ids,true);assert.equal(x.legal_conclusions_verified,false);assert.ok(x.arguments[0].evidence_ids.includes('E1'))}
});
test('rejects invalid and unknown fact citations',()=>{
 assert.throws(()=>validateArguments(data,{arguments:[{stance:'claim',claim:'错误引用',confidence:'supported_demo',fact_ids:['F999'],rule_ids:[]}]},'claimant'),/unknown_reference/);
 assert.throws(()=>validateArguments(data,{arguments:[{stance:'claim',claim:'未知事实被当作已经证实',confidence:'supported_demo',fact_ids:['F3'],rule_ids:['R1']}]},'claimant'),/unsupported_claim/);
});
test('LLM absence produces explicitly labelled structured demo',async()=>{
 const k=['LLM_API_KEY','LLM_BASE_URL','LLM_MODEL'];const prev=k.map(x=>process.env[x]);
 try{k.forEach(x=>delete process.env[x]);const r=await analyze(data,'为申请人准备论证',{role:'claimant'});assert.equal(r.mode,'structured_demo');assert.equal(r.structured.arguments.length,2)}
 finally{k.forEach((x,i)=>prev[i]===undefined?delete process.env[x]:process.env[x]=prev[i])}
});
