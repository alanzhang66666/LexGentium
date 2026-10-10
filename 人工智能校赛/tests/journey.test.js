import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../server.js';
import { buildHearing, buildReview, compareStrategies } from '../engine/journey.js';
import { readFileSync } from 'node:fs';

const data=JSON.parse(readFileSync(new URL('../data/golden-case.json',import.meta.url),'utf8'));
test('journey contracts share case and factual source identity',()=>{
 const h=buildHearing(data,'abc'), r=buildReview(data,'abc'),s=compareStrategies(data);
 assert.equal(h.session_id,r.session_id);
 assert.equal(h.case_id,s.case_id);
 assert.equal(h.mode,'synthetic_replay');
 assert.ok(r.evidence_gaps.includes('F3'));
 assert.equal(s.calculated_payoff,false);
 assert.ok(s.strategies.every(v=>v.needed_sources.every(id=>data.facts.some(f=>f.id===id))));
});
test('journey API requires same live session', async()=>{
 const server=createServer().listen(0,'127.0.0.1'); await once(server,'listening');
 const base='http://127.0.0.1:'+server.address().port;
 try{
  const session=await (await fetch(base+'/api/session',{method:'POST'})).json();
  for (const route of ['/api/hearing','/api/strategy','/api/review']){
   assert.equal((await fetch(base+route)).status,404);
   const res=await fetch(base+route+'?session_id='+session.id);
   assert.equal(res.status,200);
   const body=await res.json();
   assert.equal(body.session_id,session.id);
   assert.equal(body.case_id,data.id);
  }
  assert.equal((await fetch(base+'/strategy')).status,200);
 }finally{await new Promise(resolve=>server.close(resolve))}
});
