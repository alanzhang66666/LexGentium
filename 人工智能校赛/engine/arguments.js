// Validated argument unit. A reference ID is a pointer, not proof that a legal conclusion is correct.
const ROLES=new Set(['claimant','respondent','neutral']);
const STANCES=new Set(['claim','counterargument','issue']);
const CONFIDENCE=new Set(['supported_demo','disputed','insufficient']);
const isText=(s,max=1200)=>typeof s==='string'&&s.trim().length>0&&s.length<=max;
export function validateArguments(data,raw,role){
 if(!ROLES.has(role))throw new Error('invalid_role');
 if(!raw||typeof raw!=='object'||Array.isArray(raw)||!Array.isArray(raw.arguments)||raw.arguments.length<1||raw.arguments.length>5)throw new Error('invalid_arguments');
 const facts=new Map(data.facts.map(f=>[f.id,f]));
 const rules=new Map(data.rules.map(r=>[r.id,r]));
 const docs=new Set(data.documents.map(d=>d.id));
 const normalized=raw.arguments.map((item,i)=>{
  if(!item||typeof item!=='object'||!isText(item.claim)||!STANCES.has(item.stance)||!CONFIDENCE.has(item.confidence))throw new Error('invalid_argument_shape');
  if(!Array.isArray(item.fact_ids)||!Array.isArray(item.rule_ids)||item.fact_ids.length>8||item.rule_ids.length>8)throw new Error('invalid_reference_shape');
  if(item.fact_ids.some(id=>!facts.has(id))||item.rule_ids.some(id=>!rules.has(id)))throw new Error('unknown_reference');
  if(item.confidence==='supported_demo'&&(item.fact_ids.length===0||item.fact_ids.some(id=>facts.get(id).status==='unknown')))throw new Error('unsupported_claim');
  const evidence_ids=[...new Set(item.fact_ids.flatMap(id=>facts.get(id).source_ids||[]))];
  if(evidence_ids.some(id=>!docs.has(id)))throw new Error('unknown_evidence');
  return {id:'A'+(i+1),stance:item.stance,claim:item.claim.trim(),confidence:item.confidence,fact_ids:[...new Set(item.fact_ids)],rule_ids:[...new Set(item.rule_ids)],evidence_ids,requires_professional_review:true};
 });
 return {role,arguments:normalized,verified_reference_ids:true,legal_conclusions_verified:false};
}
export function demoArguments(data,role){
 const first=data.facts.find(f=>f.status!=='unknown');
 const unknown=data.facts.find(f=>f.status==='unknown');
 const statement=role==='claimant'?'申请人应整理合同交付与尾款请求的证据，暂不推定免责或违约成立。':role==='respondent'?'被申请人应核查验收异议与履约障碍证据，不能直接断定免责。':'双方应先核对交付、验收和付款事实，再对法律适用提出相反论证。';
 return validateArguments(data,{arguments:[
  {stance:role==='respondent'?'counterargument':role==='claimant'?'claim':'issue',claim:statement,confidence:'supported_demo',fact_ids:[first.id],rule_ids:[]},
  {stance:'issue',claim:'供应链事件能否构成免责障碍仍缺关键证据，需要补充事实。',confidence:'insufficient',fact_ids:unknown?[unknown.id]:[],rule_ids:data.rules.length?[data.rules[0].id]:[]}
 ]},role);
}
