import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../server.js';
test('analysis API requires a valid session and preserves provenance',async()=>{
 const server=createServer().listen(0,'127.0.0.1');await once(server,'listening');
 const base='http://127.0.0.1:'+server.address().port;
 try {
  const session=await (await fetch(base+'/api/session',{method:'POST'})).json();
  const response=await fetch(base+'/api/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({session_id:session.id,question:'需补哪些履约障碍证据？'})});
  assert.equal(response.status,200);
  const result=await response.json();
  assert.equal(result.session_id,session.id);
  assert.ok(['structured_demo','live_llm'].includes(result.mode));
  assert.ok(result.evidence_gaps.some(x=>x.source_id==='F3'));
  const missing=await fetch(base+'/api/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({session_id:'missing',question:'test'})});
  assert.equal(missing.status,404);
  const huge=await fetch(base+'/api/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({session_id:session.id,question:'a'.repeat(10000)})});
  assert.equal(huge.status,413);
 } finally {await new Promise(resolve=>server.close(resolve));}
});
