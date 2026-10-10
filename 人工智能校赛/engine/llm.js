import { buildAnalysis } from './legal.js';
const allowed = new Set(['https:', 'http:']);
export async function analyze(data, question) {
 const grounded = buildAnalysis(data, question);
 const key=process.env.LLM_API_KEY;
 const base=process.env.LLM_BASE_URL;
 const model=process.env.LLM_MODEL;
 if (!key || !base || !model) return grounded;
 let url;
 try {url=new URL(base.replace(/\/$/,'') + '/chat/completions');} catch {return {...grounded,mode:'structured_demo',notice:'模型端点配置无效，采用可追溯演示输出'};}
 if(!allowed.has(url.protocol) || (url.protocol!=='https:' && process.env.NODE_ENV==='production')) return {...grounded,notice:'生产环境只允许 HTTPS 模型接口'};
 const ac=new AbortController(); const timeout=setTimeout(()=>ac.abort(),10000);
 try {
   const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({model,temperature:0.1,max_tokens:550,messages:[{role:'system',content:'你是跨境商事争议准备助手。只能基于提供的合成示范事实和规则索引。unknown 一律保持未知，法律规则未经人工复核。不可预测仲裁裁决、胜诉概率、赔偿数额，不得增加事实。输出研究辅助意见且建议律师复核。'},{role:'user',content:JSON.stringify({question,case_id:data.id,facts:data.facts,rules:data.rules,issues:data.issues})}]}),signal:ac.signal});
   if(!response.ok) throw new Error('upstream_failed');
   const payload=await response.json();
   const content=payload?.choices?.[0]?.message?.content;
   if(typeof content!=='string'||!content.trim()) throw new Error('empty_upstream');
   return {...grounded,mode:'live_llm',draft:content.slice(0,5000),notice:'模型草稿未经法律复核；来源核验请以事实与规则列表为准。'};
 } catch {return {...grounded,mode:'structured_demo',notice:'实时模型不可用，已明确回退为结构化演示输出'};}
 finally {clearTimeout(timeout);}
}
