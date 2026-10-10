// Source-grounded demonstration contracts. No model can turn unknown facts into established facts.
export const FACT_STATES = new Set(['demo_assumption', 'disputed', 'verified', 'unknown']);
export function validateCase(data) {
  if (data.classification !== 'synthetic_demo') throw new Error('demo classification required');
  if (!Array.isArray(data.facts) || !Array.isArray(data.rules) || !Array.isArray(data.issues)) throw new Error('invalid case contract');
  const ids = new Set();
  for (const fact of data.facts) {
    if (!fact.id || ids.has(fact.id) || !FACT_STATES.has(fact.status) || !fact.text) throw new Error('invalid fact record');
    ids.add(fact.id);
  }
  for (const rule of data.rules) {
    if (!rule.id || ids.has(rule.id) || !rule.label || typeof rule.reviewed !== 'boolean') throw new Error('invalid rule record');
    ids.add(rule.id);
  }
  if (!Array.isArray(data.documents) || !Array.isArray(data.timeline)) throw new Error('evidence and timeline required');
  const documentIds=new Set();
  for(const doc of data.documents){
    if (!doc.id || documentIds.has(doc.id) || !doc.text || doc.classification!=='synthetic_demo') throw new Error('invalid evidence');
    documentIds.add(doc.id);
  }
  for(const fact of data.facts){
    if (!Array.isArray(fact.source_ids) || fact.source_ids.some(id=>!documentIds.has(id))) throw new Error('invalid fact references');
    if(fact.status==='unknown' && fact.source_ids.length) throw new Error('unknown facts must not cite proof');
  }
  for(const event of data.hearing)if(!Array.isArray(event.source_ids)||event.source_ids.some(id=>!documentIds.has(id)))throw new Error('invalid hearing references');
  for(const event of data.timeline)if(!Array.isArray(event.source_ids)||event.source_ids.some(id=>!documentIds.has(id)))throw new Error('invalid timeline references');
  return true;
}
export function buildAnalysis(data, prompt) {
  const question = String(prompt || '').trim();
  if (!question || question.length > 1500) throw new RangeError('question must contain 1–1500 characters');
  const known = data.facts.filter(f => f.status !== 'unknown');
  const unknown = data.facts.filter(f => f.status === 'unknown');
  return {
    mode: 'structured_demo', question, case_id: data.id,
    answer: '现有材料仅支持提出争议准备方向，不能据此直接认定违约、免责或赔偿结果。请核查合同义务、双方证据及适用法律。',
    facts: known.map(f => ({source_id: f.id, status: f.status, text: f.text, evidence_ids: f.source_ids})),
    evidence_gaps: unknown.map(f => ({source_id:f.id, text:f.text, evidence_ids:f.source_ids})),
    legal_research: data.rules.map(r => ({source_id:r.id, label:r.label, reviewed:r.reviewed, note:r.note})),
    professional_review_required: true
  };
}
export const supportedRoles = Object.freeze({ arbitrator:'首席仲裁员', claimant:'申请人代理', respondent:'被申请人代理' });
