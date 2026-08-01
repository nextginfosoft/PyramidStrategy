class SoundService {
  private enabled: boolean = false

  constructor() {
    this.enabled = localStorage.getItem('sound_alerts_enabled') !== 'false'
  }

  public isEnabled(): boolean {
    return this.enabled
  }

  public setEnabled(val: boolean) {
    this.enabled = val
    localStorage.setItem('sound_alerts_enabled', String(val))
  }

  private playTone(freqs: number[], durations: number[], type: OscillatorType = 'sine', decay = 0.3) {
    if (!this.enabled) return
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      if (!AudioCtx) return
      const ctx = new AudioCtx()
      
      let startTime = ctx.currentTime
      freqs.forEach((freq, idx) => {
        const dur = durations[idx] || 0.1
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        
        osc.type = type
        osc.frequency.setValueAtTime(freq, startTime)
        
        // Envelope decay
        gain.gain.setValueAtTime(0.08, startTime)
        gain.gain.exponentialRampToValueAtTime(0.0001, startTime + dur - 0.01)
        
        osc.connect(gain)
        gain.connect(ctx.destination)
        
        osc.start(startTime)
        osc.stop(startTime + dur)
        
        startTime += dur - 0.01
      })
    } catch (e) {
      console.warn("Sound play failed:", e)
    }
  }

  // 🔔 Rising chime for trade average-in entries (L1, L2, L3)
  public playEntryChime() {
    this.playTone([523.25, 659.25], [0.12, 0.22], 'sine') // C5 -> E5
  }

  // 🎉 Arpeggio climb chord for target hit target exits
  public playSuccessChime() {
    this.playTone([523.25, 659.25, 783.99, 1046.50], [0.08, 0.08, 0.08, 0.26], 'sine') // C5 -> E5 -> G5 -> C6
  }

  // ⚠️ Dual-tone triangle warning alarm for disconnects / errors
  public playWarningAlert() {
    this.playTone([220, 180, 220, 180], [0.1, 0.1, 0.1, 0.22], 'triangle')
  }

  // 💡 Soft bell chime for motivational quote popups
  public playMotivationalChime() {
    this.playTone([440, 554.37, 659.25], [0.15, 0.12, 0.25], 'sine') // A4 -> C#5 -> E5
  }
}

export const soundService = new SoundService()
