import type { ConflictStrategy } from "@/lib/conversation-types"
import type { Actor, Emotion, GestureClip } from "@/lib/court3d/protocol"

export const INTENSITY_CAPS: Record<string, number> = {
  judicial: 0.4,
  counsel: 0.6,
  party: 0.8,
  interpreter: 0.3,
}

export const ACTOR_CATEGORY: Record<Actor, keyof typeof INTENSITY_CAPS> = {
  judge: "judicial",
  clerk: "judicial",
  plaintiff_counsel: "counsel",
  defendant_counsel: "counsel",
  plaintiff_party: "party",
  defendant_party: "party",
  interpreter: "interpreter",
}

export interface Annotation {
  emotion: Emotion
  intensity: number
  gesture: GestureClip | null
}

export function annotateSentence(
  sentence: string,
  actor: Actor,
  strategy?: ConflictStrategy | null,
  intensityCap?: number,
): Annotation {
  const cap = intensityCap ?? INTENSITY_CAPS[ACTOR_CATEGORY[actor]] ?? 0.5
  let emotion: Emotion = actor === "judge" ? "stern" : "neutral"
  let intensity = 0.25
  let gesture: GestureClip | null = null

  if (/[？?]/.test(sentence)) {
    emotion = "questioning"
    intensity = 0.4
    gesture = "lean_forward"
  }
  if (/[！!]/.test(sentence)) {
    intensity += 0.15
  }
  if (/反对|否认|驳回|不能成立|毫无|虚假/.test(sentence)) {
    emotion = "assertive"
    intensity = Math.max(intensity, 0.65)
    gesture = "point"
  } else if (/同意|认可|接受|没有异议|可以调解/.test(sentence)) {
    emotion = "conciliatory"
    intensity = Math.max(intensity, 0.35)
    gesture = "nod"
  } else if (/调解|协商|和解/.test(sentence)) {
    emotion = "calm"
    gesture = gesture ?? "hand_over_doc"
  } else if (/判决|宣判|裁定/.test(sentence)) {
    emotion = "stern"
    gesture = "stand"
    intensity = Math.max(intensity, 0.45)
  } else if (/举证|证据|质证/.test(sentence)) {
    emotion = "attentive"
    gesture = "flip_file"
  } else if (/回避|权利|义务|开庭/.test(sentence)) {
    emotion = "stern"
    gesture = actor === "clerk" ? "type" : "nod"
  }

  if (strategy === "competing") {
    intensity += 0.12
    gesture = gesture ?? "lean_forward"
    if (emotion === "neutral") emotion = "assertive"
  } else if (strategy === "avoiding") {
    intensity -= 0.08
    if (emotion === "neutral") emotion = "tense"
  } else if (strategy === "collaborating" || strategy === "accommodating") {
    if (emotion === "neutral") emotion = "calm"
    gesture = gesture ?? "nod"
  } else if (strategy === "compromising") {
    if (emotion === "neutral") emotion = "conciliatory"
  }

  if (actor === "judge" && !gesture) gesture = "nod"
  if (actor === "clerk" && !gesture) gesture = "type"

  return {
    emotion,
    intensity: clamp(intensity, 0.12, cap),
    gesture,
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}
