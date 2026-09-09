export function visemeFromCharIndex(text: string, charIndex: number): number {
  const ch = text[Math.min(charIndex, text.length - 1)] ?? ""
  if (/[aeiouAEIOU啊啊哦喔呜吁]/.test(ch)) return 0.85
  if (/[iyIY衣依]/.test(ch)) return 0.45
  if (/[bpmBPM波不]/.test(ch)) return 0.15
  if (/\s/.test(ch)) return 0.05
  return 0.4
}

export function createAmplitudeLipsync(analyser: AnalyserNode) {
  const data = new Uint8Array(analyser.frequencyBinCount)
  return () => {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128
      sum += v * v
    }
    return Math.min(1, Math.sqrt(sum / data.length) * 4)
  }
}
