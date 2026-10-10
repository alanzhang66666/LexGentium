import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from '../server.js';

test('SVG hearing UI module and replay share the same session contract',async()=>{
 const server=createServer().listen(0,'127.0.0.1');await once(server,'listening');
 const base='http://127.0.0.1:'+server.address().port;
 try {
   const file=await fetch(base+'/hearing-ui.js');
   assert.equal(file.status,200);
   assert.match(file.headers.get('content-type'),/javascript/);
   const source=await file.text();
   assert.match(source,/export async function mountHearing/);
   assert.match(source,/hearing-scene/);
   assert.match(source,/session_id/);
   const page=await (await fetch(base+'/hearing-3d')).text();
   assert.match(page,/hearing-visual/);
   assert.match(page,/hearing-ui\.js/);
   const session=await (await fetch(base+'/api/session',{method:'POST'})).json();
   const replay=await (await fetch(base+'/api/hearing?session_id='+session.id)).json();
   assert.equal(replay.session_id,session.id);
   assert.equal(replay.mode,'synthetic_replay');
   assert.deepEqual(replay.events.map(e=>e.role),['arbitrator','claimant','respondent','arbitrator']);
 }finally{await new Promise(resolve=>server.close(resolve))}
});
