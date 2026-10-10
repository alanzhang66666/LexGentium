import { buildAnalysis } from './legal.js';
import { demoArguments,validateArguments } from './arguments.js';
function approvedEndpoint(url){
 if(url.protocol!=='https:' || url.username || url.password || url.port || url.hash || url.search)return false;
 const hosts=(process.env.LLM_ALLOWED_HOSTS||'').split(',').map(h=>h.trim().toLowerCase()).filter(Boolean);
 return hosts.length>0 && hosts.includes(url.hostname.toLowerCase()) && !/^\d+\.\d+\.\d+\.\d+$/.test(url.hostname);
}
export async function analyze(data, question, options={}) {
 const role=options.role||'neutral';
 const grounded = {...buildAnalysis(data, question),role,structured:demoArguments(data,role)};
 const key=process.env.LLM_API_KEY;
 const base=process.env.LLM_BASE_URL;
 const model=process.env.LLM_MODEL;
 if (!key || !base || !model) return grounded;
 let url;
 try {url=new URL(base.replace(/\/$/,'') + '/chat/completions');} catch {return {...grounded,mode:'structured_demo',notice:'模型端点配置无效，采用可追溯演示输出'};}
 if(!approvedEndpoint(url)) return {...grounded,mode:'structured_demo',notice:'模型端点未进入 HTTPS 主机白名单；采用结构化演示'};
 const ac=new AbortController(); const timeout=setTimeout(()=>ac.abort(),10000);
 try {
   const response=await fetch(url,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({model,temperature:0.1,max_tokens:550,messages:[{role:'system',content:'你是跨境商事争议准备助手。根据 user 内容的 role（claimant 为申请人代理，respondent 为被申请人代理，neutral 为中立助手）分别准备争议分析。只能基于提供的合成示范事实和规则索引。unknown 一律保持未知，法律规则未经人工复核。不可预测仲裁裁决、胜诉概率、赔偿数额，不得增加事实。仅输出严格 JSON 对象，格式 {"arguments":[{"stance":"claim|counterargument|issue","claim":"论证内容","confidence":"supported_demo|disputed|insufficient","fact_ids":["F1"],"rule_ids":["R1"]}]}。所有引用必须存在于输入中，未知事实只能用 insufficient。输出研究辅助意见且建议律师复核。'},{role:'user',content:JSON.stringify({question,role:options.role||'neutral',case_id:data.id,facts:data.facts,rules:data.rules,issues:data.issues})}]}),signal:ac.signal});
   if(!response.ok) throw new Error('upstream_failed');
   const payload=await response.json();
   const content=payload?.choices?.[0]?.message?.content;
   if(typeof content!=='string'||!content.trim()) throw new Error('empty_upstream');
   const candidate=JSON.parse(content.replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,''));
   const structured=validateArguments(data,candidate,role);
   return {...grounded,mode:'live_llm',structured,notice:'引用 ID 已校验，但模型法律论证未经人工复核。'};
 } catch {return {...grounded,mode:'structured_demo',notice:'模型不可用或结构化论证未通过校验，采用有明确标识的演示分析'};}
 finally {clearTimeout(timeout);}
}
