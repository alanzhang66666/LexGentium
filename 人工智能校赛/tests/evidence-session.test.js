import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createServer } from '../server.js';
import { validateCase } from '../engine/legal.js';
import { buildHearing } from '../engine/journey.js';
const data=JSON.parse(readFileSync(new URL('../data/golden-case.json',import.meta.url),'utf8'));
test('golden case provenance and hearing references',()=>{
 assert.equal(validateCase(data),true);
 assert.equal(data.documents.length,4);
 const ids=new Set(data.documents.map(x=>x.id));
 assert.ok(data.facts.every(f=>f.source_ids.every(id=>ids.has(id))));
 assert.deepEqual(buildHearing(data,'example').events[3].source_ids,[]);
});
test('role-specific analysis is linked to the live session review',async()=>{
 const server=createServer().listen(0,'127.0.0.1'); await once(server,'listening');
 const base='http://127.0.0.1:'+server.address().port;
 try{
  const session=await (await fetch(base+'/api/session',{method:'POST'})).json();
  const result=await fetch(base+'/api/analyze',{method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({session_id:session.id,role:'claimant',question:'申请方需要补哪些证据？'})});
  assert.equal(result.status,200);
  const analysis=await result.json();
  assert.equal(analysis.role,'claimant');
  assert.ok(analysis.analysis_id);
  const review=await (await fetch(base+'/api/review?session_id='+session.id)).json();
  assert.equal(review.mode,'session_report');
  assert.equal(review.analysis_count,1);
  assert.equal(review.analysis_history[0].role,'claimant');
  assert.ok(review.evidence_gaps.includes('F3'));
  const bad=await fetch(base+'/api/analyze',{method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({session_id:session.id,role:'arbitrator',question:'test'})});
  assert.equal(bad.status,400);
 }finally{await new Promise(resolve=>server.close(resolve))}
});
