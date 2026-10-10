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
  return {session_id:sessionId,case_id:data.id,mode:'synthetic_replay',events:data.hearing.map(event=>({...event,source_ids:event.source_ids||[]}))};
}
export function buildReview(data,sessionId,history=[]) {
  const evaluated=history.filter(x=>x && ['structured_demo','live_llm'].includes(x.mode));
  const dimensions=[
    {label:'法律依据',status:'待法律复核',detail:'规则材料尚未独立复核；本场保存 '+evaluated.length+' 次辅助分析。'},
    {label:'事实一致性',status:'有证据缺口',detail:'未知事实：'+data.facts.filter(f=>f.status==='unknown').map(f=>f.id).join('、')+'。'},
    {label:'程序合规',status:'模拟记录',detail:'仅有 '+data.hearing.length+' 条合成事件，尚未执行正式程序合规量表。'},
    {label:'策略效果',status:'定性比较',detail:'没有 GameEngine 实测收益或胜诉概率。'}
  ];
  return {session_id:sessionId,case_id:data.id,mode:'session_report',dimensions,
    evidence_gaps:data.facts.filter(f=>f.status==='unknown').map(f=>f.id),
    analysis_count:evaluated.length,
    analysis_history:evaluated.map(x=>({id:x.id,role:x.role,question:x.question,mode:x.mode,created_at:x.created_at,source_ids:x.source_ids})),
    formal_legal_review:false};
}
