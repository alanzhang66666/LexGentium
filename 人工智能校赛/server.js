import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { validateCase, buildAnalysis } from './engine/legal.js';
import { analyze } from './engine/llm.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const caseData = JSON.parse(await readFile(path.join(here, 'data/golden-case.json'), 'utf8'));
validateCase(caseData);
const html = await readFile(path.join(here, 'public/index.html'), 'utf8');
const sessions = new Map();
const pages = new Set(['/', '/global-dispute', '/research', '/conversation', '/hearing-3d', '/evaluation']);
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
  if (req.method === 'GET' && url.pathname === '/api/health') return send(res, 200, { status:'ok', mode:'synthetic_replay', version:'0.1.0', port:8080 });
  if (req.method === 'GET' && url.pathname === '/api/case') return send(res, 200, caseData);
  if (req.method === 'POST' && url.pathname === '/api/analyze') {
    let body;
    try {body=await readJSON(req);}catch(err){return send(res,err.status||400,{error:err.message});}
    if (!body || typeof body.question!=='string') return send(res,400,{error:'question_required'});
    if (typeof body.session_id!=='string' || !sessions.has(body.session_id)) return send(res,404,{error:'session_not_found'});
    let response;
    try {response=await analyze(caseData,body.question);}catch(err){return send(res,400,{error:'invalid_question'});}
    return send(res,200,{...response,session_id:body.session_id});
  }
  if (req.method === 'POST' && url.pathname === '/api/session') {
    if (sessions.size >= 200) sessions.delete(sessions.keys().next().value);
    const id = randomUUID();
    sessions.set(id, { id, caseId:caseData.id, mode:'synthetic_replay', createdAt:new Date().toISOString() });
    return send(res, 201, sessions.get(id));
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/session/')) {
    const id = url.pathname.slice('/api/session/'.length);
    if (!/^[0-9a-f-]{36}$/i.test(id) || !sessions.has(id)) return send(res,404,{error:'session_not_found'});
    return send(res,200,sessions.get(id));
  }
  if (req.method === 'GET' && pages.has(url.pathname)) return send(res,200,html,'text/html; charset=utf-8');
  return send(res,404,{error:'not_found'});
}
export function createServer() { return http.createServer(handler); }
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 8080);
  createServer().listen(port, '0.0.0.0', () => console.log('LexGentium school edition listening on ' + port));
}
