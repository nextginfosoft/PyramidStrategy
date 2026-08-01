import { useEffect, useState } from 'react'
import { useGamificationStore } from '../../store/gamificationStore'
import { soundService } from '../../services/sound'

export function MotivationalToast() {
  const { currentQuote, dismissQuote } = useGamificationStore()
  const [isVisible, setIsVisible] = useState(false)
  const [progress, setProgress] = useState(100)

  useEffect(() => {
    if (currentQuote) {
      setIsVisible(true)
      setProgress(100)

      // Play motivational chime
      soundService.playMotivationalChime()

      // Animate progress bar
      const startTime = Date.now()
      const duration = currentQuote.duration

      const interval = setInterval(() => {
        const elapsed = Date.now() - startTime
        const remaining = Math.max(0, 100 - (elapsed / duration) * 100)
        setProgress(remaining)

        if (remaining <= 0) {
          clearInterval(interval)
        }
      }, 100)

      return () => clearInterval(interval)
    } else {
      setIsVisible(false)
    }
  }, [currentQuote])

  const handleDismiss = () => {
    setIsVisible(false)
    setTimeout(dismissQuote, 300) // Wait for fade-out animation
  }

  if (!currentQuote) return null

  // Determine accent color based on event type
  const getAccentColor = () => {
    const { eventType } = currentQuote
    if (eventType === 'TARGET_HIT') return { border: '#10b981', glow: 'shadow-emerald-500/20', progressBg: 'bg-emerald-500' }
    if (eventType === 'SL_HIT') return { border: '#ef4444', glow: 'shadow-red-500/20', progressBg: 'bg-red-500' }
    if (eventType.startsWith('ENTRY_L3')) return { border: '#f97316', glow: 'shadow-orange-500/20', progressBg: 'bg-orange-500' }
    if (eventType.startsWith('ENTRY_')) return { border: '#f59e0b', glow: 'shadow-amber-500/20', progressBg: 'bg-amber-500' }
    if (eventType === 'ENGINE_START') return { border: '#3b82f6', glow: 'shadow-blue-500/20', progressBg: 'bg-blue-500' }
    return { border: '#a78bfa', glow: 'shadow-purple-500/20', progressBg: 'bg-purple-500' }
  }

  const accent = getAccentColor()

  return (
    <div
      className={`fixed bottom-6 right-6 z-[9998] transition-all duration-300 ${
        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'
      }`}
    >
      <div
        className={`w-[400px] rounded-2xl border backdrop-blur-xl bg-gray-900/90 ${accent.glow} shadow-2xl overflow-hidden`}
        style={{ borderColor: accent.border, borderWidth: '1px' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{ background: `linear-gradient(90deg, ${accent.border}15, transparent)` }}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">{currentQuote.emoji}</span>
            <span className="text-[11px] font-semibold tracking-wide uppercase text-gray-300">
              Motivational Moment
            </span>
          </div>
          <button
            onClick={handleDismiss}
            className="text-gray-500 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10 text-xs leading-none"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          {/* Quote */}
          <p className="text-gray-200 text-sm leading-relaxed italic font-light">
            &ldquo;{currentQuote.quote}&rdquo;
          </p>
          <p className="text-right mt-2 text-xs font-medium" style={{ color: accent.border }}>
            — {currentQuote.author}
          </p>

          {/* Context */}
          <div className="mt-3 flex items-center gap-3 text-[10px] text-gray-400">
            <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10">
              {currentQuote.label}
            </span>
            {currentQuote.side && (
              <span className={`px-2 py-0.5 rounded-full ${
                currentQuote.side === 'CE' 
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {currentQuote.side} {currentQuote.level}
              </span>
            )}
          </div>

          {/* SL Active warning for L3 */}
          {currentQuote.extra?.sl_price && (
            <div className="mt-2 text-[10px] text-orange-400 flex items-center gap-1">
              <span>🛡️</span>
              <span>SL Active at ₹{String(currentQuote.extra.sl_price)}</span>
            </div>
          )}

          {/* Cool down for SL hit */}
          {currentQuote.eventType === 'SL_HIT' && (
            <div className="mt-2 text-[10px] text-red-400 flex items-center gap-1">
              <span>⏸️</span>
              <span>Cool down recommended: 5 minutes</span>
            </div>
          )}
        </div>

        {/* Progress Bar */}
        <div className="h-1 bg-gray-800 w-full">
          <div
            className={`h-full ${accent.progressBg} transition-all duration-100 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  )
}
