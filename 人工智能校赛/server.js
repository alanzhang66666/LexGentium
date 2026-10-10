import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { validateCase, buildAnalysis } from './engine/legal.js';
import { analyze } from './engine/llm.js';
import { competitionPrompts,getPrompt } from './engine/prompts.js';
import { sessionValid,allowAnalysis,finishAnalysis } from './engine/limits.js';
import { buildHearing, buildReview, compareStrategies } from './engine/journey.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const caseData = JSON.parse(await readFile(path.join(here, 'data/golden-case.json'), 'utf8'));
validateCase(caseData);
const html = await readFile(path.join(here, 'public/index.html'), 'utf8');
const hearingScript = await readFile(path.join(here, 'public/hearing-ui.js'), 'utf8');
const sessions = new Map();
const pages = new Set(['/', '/global-dispute', '/research', '/conversation', '/hearing-3d', '/strategy', '/evaluation']);
const send = (res, code, value, contentType = 'application/json; charset=utf-8') => {
  res.writeHead(code, { 'Content-Type': contentType, 'Cache-Control': 'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer' });
  res.end(contentType.startsWith('application/json') ? JSON.stringify(value) : value);
};
async function readJSON(req) {
  let size=0; const chunks=[];
  for await (const chunk of req) { size += chunk.length; if(size>8192){const err=new Error('too_large');err.status=413;throw err;} chunks.push(chunk); }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch {const err=new Error('invalid_json');err.status=400;throw err;}
}
export async function handler(req, res) {
  let url;
  try { url = new URL(req.url, 'http://localhost'); } catch { return send(res, 400, { error: 'invalid_url' }); }
  if (req.method === 'GET' && url.pathname === '/hearing-ui.js') return send(res,200,hearingScript,'text/javascript; charset=utf-8');
  if (req.method === 'GET' && url.pathname === '/api/health') return send(res, 200, { status:'ok', mode:'synthetic_replay', version:'0.1.0', port:8080 });
  if (req.method === 'GET' && url.pathname === '/api/prompts') return send(res,200,{prompts:competitionPrompts});
  if (req.method === 'GET' && url.pathname === '/api/case') return send(res, 200, caseData);
  if (req.method === 'GET' && ['/api/hearing','/api/strategy','/api/review'].includes(url.pathname)) {
    const sid=url.searchParams.get('session_id');
    if (!sid || !sessionValid(sessions,sid)) return send(res,404,{error:'session_not_found'});
    if (url.pathname==='/api/hearing') return send(res,200,buildHearing(caseData,sid));
    if (url.pathname==='/api/strategy') return send(res,200,{...compareStrategies(caseData),session_id:sid});
    return send(res,200,buildReview(caseData,sid,sessions.get(sid).analyses));
  }
  if (req.method === 'POST' && url.pathname === '/api/analyze') {
    let body;
    try {body=await readJSON(req);}catch(err){return send(res,err.status||400,{error:err.message});}
    if (!body || (typeof body.question!=='string' && typeof body.prompt_id!=='string')) return send(res,400,{error:'question_required'});
    if(body.prompt_id){const predefined=getPrompt(body.prompt_id);if(!predefined)return send(res,400,{error:'invalid_prompt'});body.question=predefined.question;body.role=predefined.role;}
    if (typeof body.session_id!=='string' || !sessionValid(sessions,body.session_id)) return send(res,404,{error:'session_not_found'});
    if (body.role!==undefined && !['claimant','respondent','neutral'].includes(body.role)) return send(res,400,{error:'invalid_role'});
    body.role=body.role||'neutral';
    const session=sessions.get(body.session_id);
    const limit=allowAnalysis(session);
    if(!limit.ok)return send(res,limit.status,{error:limit.reason});
    let response;
    try {response=await analyze(caseData,body.question,{role:body.role});}catch(err){return send(res,400,{error:'invalid_question'});}finally{finishAnalysis(session)}
    const stored={id:randomUUID(),role:body.role,question:body.question,mode:response.mode,
      source_ids:[...new Set((response.structured?.arguments||[]).flatMap(a=>[...a.fact_ids,...a.rule_ids,...a.evidence_ids]))],
      created_at:new Date().toISOString(),output:response};
    session.analyses.push(stored);
    if(session.analyses.length>20)session.analyses.shift();
    return send(res,200,{...response,analysis_id:stored.id,session_id:body.session_id});
  }
  if (req.method === 'POST' && url.pathname === '/api/session') {
    if (sessions.size >= 200) sessions.delete(sessions.keys().next().value);
    const id = randomUUID();
    sessions.set(id, { id, caseId:caseData.id, mode:'synthetic_replay', createdAt:new Date().toISOString(),analyses:[],analysis_count_total:0,inflight:false });
    return send(res, 201, sessions.get(id));
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/session/')) {
    const id = url.pathname.slice('/api/session/'.length);
    if (!/^[0-9a-f-]{36}$/i.test(id) || !sessionValid(sessions,id)) return send(res,404,{error:'session_not_found'});
    const record=sessions.get(id); return send(res,200,{id:record.id,caseId:record.caseId,mode:record.mode,createdAt:record.createdAt,analysis_count:record.analyses.length});
  }
  if (req.method === 'GET' && pages.has(url.pathname)) return send(res,200,html,'text/html; charset=utf-8');
  return send(res,404,{error:'not_found'});
}
export function createServer() { return http.createServer(handler); }
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 8080);
  createServer().listen(port, '0.0.0.0', () => console.log('LexGentium school edition listening on ' + port));
}
