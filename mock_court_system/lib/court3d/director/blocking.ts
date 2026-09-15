import type { CourtStage, CourtSubStage } from "@/lib/conversation-types"
import type { Actor, CameraShot, PerformanceEvent, RoomId } from "@/lib/court3d/protocol"

export interface BlockingCue {
  room: RoomId
  shot: CameraShot
  focus: Actor
  evidenceLit: boolean
  stand: Actor[]
  clerkLine?: string
}

const CLERK_LINES: Partial<Record<CourtSubStage, string>> = {
  opening_identity: "现在开庭。请双方当事人及其代理人核实身份。",
  opening_composition: "本案由审判长主持审理，书记员担任记录。",
  opening_rights: "双方当事人依法享有申请回避、陈述事实、举证质证和辩论等诉讼权利。",
  opening_recusal: "请双方确认是否申请回避。",
  opening_absence: "当事人无正当理由拒不到庭的，将依法缺席审理。",
  investigation_claim: "现在进行法庭调查。请原告陈述诉讼请求和事实理由。",
  investigation_defense: "请被告进行答辩。",
  investigation_evidence: "请双方出示证据，并由对方质证。",
  investigation_cross_exam: "现在进行质证。",
  debate_focus: "法庭归纳本案争议焦点如下，请双方围绕焦点发表意见。",
  debate_final_statement: "法庭辩论终结。请双方作最后陈述。",
  mediation_ask: "根据法律规定，现在征求双方是否同意调解。",
  judgment_generating: "全体起立，现在宣判。",
}

export function blockingFor(
  stage: CourtStage,
  subStage?: CourtSubStage | null,
  roomHint?: RoomId,
): BlockingCue {
  if (stage === "dialogue") {
    return {
      room: roomHint ?? "lawyer_office",
      shot: "two_shot",
      focus: "plaintiff_counsel",
      evidenceLit: false,
      stand: [],
    }
  }

  const room: RoomId = stage === "mediation" ? "mediation" : "courtroom"
  const cue: BlockingCue = {
    room,
    shot: "wide",
    focus: "judge",
    evidenceLit: false,
    stand: [],
    clerkLine: subStage ? CLERK_LINES[subStage] : undefined,
  }

  switch (subStage) {
    case "opening_identity":
    case "opening_composition":
    case "opening_rights":
    case "opening_recusal":
    case "opening_absence":
      cue.shot = "close_up"
      cue.focus = "judge"
      break
    case "investigation_claim":
      cue.shot = "over_shoulder"
      cue.focus = "plaintiff_counsel"
      break
    case "investigation_defense":
      cue.shot = "over_shoulder"
      cue.focus = "defendant_counsel"
      break
    case "investigation_evidence":
    case "investigation_cross_exam":
      cue.shot = "two_shot"
      cue.focus = "plaintiff_counsel"
      cue.evidenceLit = true
      break
    case "debate_focus":
      cue.shot = "close_up"
      cue.focus = "judge"
      break
    case "debate_argument":
      cue.shot = "over_shoulder"
      cue.focus = "plaintiff_counsel"
      break
    case "debate_rebuttal":
      cue.shot = "over_shoulder"
      cue.focus = "defendant_counsel"
      break
    case "debate_final_statement":
      cue.shot = "two_shot"
      cue.focus = "judge"
      break
    case "mediation_ask":
    case "mediation_plaintiff_resp":
    case "mediation_defendant_resp":
    case "mediation_announce":
      cue.room = "mediation"
      cue.shot = "two_shot"
      cue.focus = "judge"
      break
    case "judgment_generating":
    case "judgment_done":
      cue.shot = "wide"
      cue.focus = "judge"
      cue.stand = [
        "judge",
        "clerk",
        "plaintiff_counsel",
        "plaintiff_party",
        "defendant_counsel",
        "defendant_party",
        "interpreter",
      ]
      break
    default:
      break
  }

  return cue
}

export function sceneEvents(
  stage: CourtStage,
  subStage: CourtSubStage | null | undefined,
  roomHint?: RoomId,
): PerformanceEvent[] {
  const cue = blockingFor(stage, subStage, roomHint)
  const events: PerformanceEvent[] = [
    { kind: "scene", stage, subStage, room: cue.room },
    { kind: "camera", shot: cue.shot, focus: cue.focus },
    { kind: "status", evidenceLit: cue.evidenceLit, standing: Object.fromEntries(cue.stand.map((a) => [a, true])) },
  ]
  if (cue.clerkLine) {
    events.push({
      kind: "speak",
      actor: "clerk",
      sentence: cue.clerkLine,
      emotion: "stern",
      intensity: 0.28,
      speechKind: "scripted",
    })
    events.push({ kind: "gesture", actor: "clerk", clip: "type" })
  }
  return events
}

export { CLERK_LINES }
