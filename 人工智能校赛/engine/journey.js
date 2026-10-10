// Explicitly qualitative strategy scenarios; never represent them as success probabilities.
export function compareStrategies(data) {
  const sourceIds = data.facts.map(f=>f.id);
  if (!sourceIds.includes('F3')) throw new Error('missing evidence-gap reference');
  return {
    case_id:data.id, mode:'qualitative_scenarios', calculated_payoff:false,
    disclaimer:'以下为合成案例的情景准备建议，不是 GameEngine 实测、胜诉概率或正式法律意见。',
    strategies:[
      {id:'prepare_evidence',title:'补全证据后再确定请求',benefit:'避免在关键事实不清时过早作出免责或违约判断',risk:'可能增加调查与准备时间',needed_sources:['F1','F2','F3']},
      {id:'negotiate',title:'探索商事和解',benefit:'为交付、验收和尾款安排提供谈判空间',risk:'目前不能量化让步成本或争议金额',needed_sources:['F2','F3']},
      {id:'arbitration',title:'准备仲裁申请与答辩',benefit:'明确争议焦点和举证计划',risk:'仲裁协议、适用规则及关键证据仍需专业审查',needed_sources:['F1','F2','F3']}
    ]
  };
}
export function buildHearing(data, sessionId) {
  return {session_id:sessionId,case_id:data.id,mode:'synthetic_replay',events:data.hearing.map(event=>({...event,source_ids:['F1','F2','F3']}))};
}
export function buildReview(data,sessionId) {
  return {session_id:sessionId,case_id:data.id,mode:'demo_status',dimensions:data.evaluation,evidence_gaps:data.facts.filter(f=>f.status==='unknown').map(f=>f.id),formal_legal_review:false};
}
