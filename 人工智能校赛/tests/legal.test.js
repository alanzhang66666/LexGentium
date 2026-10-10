import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateCase,buildAnalysis } from '../engine/legal.js';
import { analyze } from '../engine/llm.js';
const data=JSON.parse(readFileSync(new URL('../data/golden-case.json',import.meta.url),'utf8'));
test('case contract and provenance',()=>{assert.equal(validateCase(data),true);const x=buildAnalysis(data,'请分析第79条');assert.equal(x.mode,'structured_demo');assert.ok(x.evidence_gaps.some(f=>f.source_id==='F3'));assert.ok(x.legal_research.every(x=>x.reviewed===false));});
test('rejects empty or oversize questions',()=>{assert.throws(()=>buildAnalysis(data,''),RangeError);assert.throws(()=>buildAnalysis(data,'x'.repeat(1501)),RangeError);});
test('model fallback never pretends to be live',async()=>{const keys=['LLM_API_KEY','LLM_BASE_URL','LLM_MODEL'];const previous=keys.map(k=>process.env[k]);try{keys.forEach(k=>delete process.env[k]);const r=await analyze(data,'哪些证据缺失');assert.equal(r.mode,'structured_demo');}finally{keys.forEach((k,i)=>previous[i]===undefined?delete process.env[k]:process.env[k]=previous[i]);}});
