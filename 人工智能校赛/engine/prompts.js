export const competitionPrompts=Object.freeze([
 {id:'P1',role:'claimant',title:'申请方仲裁请求准备',question:'请识别本案申请方可以提出的主要仲裁请求，并仅依据现有案件材料说明理由。'},
 {id:'P2',role:'respondent',title:'被申请方抗辩准备',question:'被申请方针对交付延期和 CISG 第79条主张有哪些主要抗辩路径？'},
 {id:'P3',role:'neutral',title:'争议策略替代方案',question:'如果申请方从竞争型策略调整为合作型策略，对当前争议解决可能产生什么影响？'}
]);
export function getPrompt(id){return competitionPrompts.find(p=>p.id===id)||null}
