import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../server.js';

test('health, synthetic case, session and all competition pages', async () => {
 const server = createServer().listen(0, '127.0.0.1');
 await once(server, 'listening');
 const base='http://127.0.0.1:'+server.address().port;
 try {
   const health=await fetch(base+'/api/health');
   assert.equal(health.status,200);
   assert.equal((await health.json()).mode,'synthetic_replay');
   const caseResponse=await fetch(base+'/api/case');
   const data=await caseResponse.json();
   assert.equal(data.classification,'synthetic_demo');
   assert.equal(data.facts.some(f=>f.status==='unknown'),true);
   const created=await fetch(base+'/api/session',{method:'POST'});
   assert.equal(created.status,201);
   const session=await created.json();
   assert.equal(session.caseId,data.id);
   assert.equal((await fetch(base+'/api/session/'+session.id)).status,200);
   assert.equal((await fetch(base+'/api/session/nonexistent')).status,404);
   for(const path of ['/', '/global-dispute', '/research', '/conversation', '/hearing-3d', '/evaluation']) {
     const response=await fetch(base+path);
     assert.equal(response.status,200,path);
     assert.match(await response.text(),/法序智演 LexGentium/);
   }
 } finally { await new Promise((resolve,reject)=>server.close(err=>err?reject(err):resolve())); }
});
