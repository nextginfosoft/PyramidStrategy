import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useStrategyStore } from '../../store/strategyStore'
import { aiApi } from '../../services/api'
import { format } from 'date-fns'
import clsx from 'clsx'

interface ApiSuggestion {
  id: number
  trade_date: string
  event: string
  side: string | null
  level: string | null
  nifty_ltp: number | null
  provider: string
  suggestion: string
  created_at: string
}

interface PreMarketBrief {
  success: boolean
  error?: string
  vix: number
  vix_analysis?: string
  expected_range?: string
  level_assessment?: string
  suggested_config?: {
    s1: number; s2: number; s3: number
    r1: number; r2: number; r3: number
  } | null
  quality_score?: number
  quality_reason?: string
}

interface PostSessionReview {
  success: boolean
  error?: string
  what_worked?: string
  what_didnt_work?: string
  patterns_observed?: string
  future_advice?: string
}

export function AIObserver() {
  const [activeTab, setActiveTab] = useState<'live' | 'pre' | 'post'>('live')
  const wsSuggestions = useStrategyStore((s) => s.aiSuggestions)

  // 1. Live suggestions query
  const { data: apiSuggestions, isLoading: isLiveLoading } = useQuery<ApiSuggestion[]>({
    queryKey: ['ai-suggestions'],
    queryFn: () => aiApi.getSuggestions(20),
    refetchInterval: 15_000,
    retry: false,
    enabled: activeTab === 'live'
  })

  // 2. Pre-market brief query
  const { data: preMarket, isLoading: isPreLoading, refetch: refetchPre } = useQuery<PreMarketBrief>({
    queryKey: ['ai-pre-market'],
    queryFn: () => aiApi.getPreMarketBrief(),
    enabled: activeTab === 'pre',
    staleTime: 60_000,
  })

  // 3. Post-session review query
  const { data: postSession, isLoading: isPostLoading, refetch: refetchPost } = useQuery<PostSessionReview>({
    queryKey: ['ai-post-session'],
    queryFn: () => aiApi.getPostSessionReview(),
    enabled: activeTab === 'post',
    staleTime: 60_000,
  })

  const hasWs = wsSuggestions.length > 0
  const hasApi = apiSuggestions && apiSuggestions.length > 0

  return (
    <div className="flex flex-col gap-2">
      {/* Tabs */}
      <div className="flex border-b border-navy-800 pb-1.5 gap-1">
        {(['live', 'pre', 'post'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-2.5 py-1 text-[10px] uppercase font-bold tracking-wider rounded transition-all focus:outline-none',
              activeTab === tab
                ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                : 'text-navy-300 hover:text-navy-100 hover:bg-navy-850'
            )}
          >
            {tab === 'live' ? '⚡ Live' : tab === 'pre' ? '🌅 Pre-Market' : '🌆 Post-Session'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="max-h-64 overflow-auto scrollbar-thin space-y-2.5 pr-0.5">
        
        {/* TAB 1: LIVE SUGGESTIONS */}
        {activeTab === 'live' && (
          <>
            {!hasWs && !hasApi && !isLiveLoading && (
              <div className="text-navy-300 text-[11px] text-center py-6">
                🤖 AI Observer watching...
                <br />
                <span className="text-[10px] text-navy-400">Suggestions appear after trade events</span>
              </div>
            )}

            {isLiveLoading && !hasWs && !hasApi && (
              <div className="space-y-2 py-2">
                <div className="h-12 bg-navy-850 rounded animate-pulse" />
                <div className="h-12 bg-navy-850 rounded animate-pulse" />
              </div>
            )}

            {/* Live WS suggestions */}
            {wsSuggestions.map((s, i) => (
              <div key={`ws-${i}`} className="bg-navy-850 border border-blue-900/40 rounded p-2.5 transition-colors">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] text-blue-400 font-bold uppercase tracking-wider">🤖 AI</span>
                  {s.side && (
                    <span className={clsx('text-[10px] font-bold px-1 rounded uppercase',
                      s.side === 'CE' ? 'bg-green-950/40 text-green-400' : 'bg-red-950/40 text-red-400')}>
                      {s.side}
                    </span>
                  )}
                  <span className="text-[10px] text-navy-300 font-semibold">{s.event}</span>
                  <span className="text-[9px] text-navy-400 font-mono ml-auto">
                    {format(s.ts, 'HH:mm:ss')}
                  </span>
                </div>
                <p className="text-[11px] text-navy-100 leading-relaxed font-mono">{s.text}</p>
              </div>
            ))}

            {/* DB suggestions */}
            {!hasWs && apiSuggestions?.map((s) => (
              <div key={`api-${s.id}`} className="bg-navy-850 border border-navy-800 rounded p-2.5">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] text-blue-400 font-bold uppercase tracking-wider">🤖 {s.provider?.toUpperCase()}</span>
                  {s.side && (
                    <span className={clsx('text-[10px] font-bold px-1 rounded uppercase',
                      s.side === 'CE' ? 'bg-green-950/40 text-green-400' : 'bg-red-950/40 text-red-400')}>
                      {s.side}
                    </span>
                  )}
                  <span className="text-[10px] text-navy-300 font-semibold">{s.event}</span>
                  {s.nifty_ltp && (
                    <span className="text-[9px] text-navy-400 font-mono">NIFTY: {s.nifty_ltp}</span>
                  )}
                  <span className="text-[9px] text-navy-400 font-mono ml-auto">
                    {s.created_at ? format(new Date(s.created_at), 'HH:mm') : ''}
                  </span>
                </div>
                <p className="text-[11px] text-navy-100 leading-relaxed font-mono">{s.suggestion}</p>
              </div>
            ))}
          </>
        )}

        {/* TAB 2: PRE-MARKET BRIEF */}
        {activeTab === 'pre' && (
          <div className="space-y-2.5 text-[11px]">
            {isPreLoading && (
              <div className="space-y-2.5 py-2">
                <div className="h-6 w-1/3 bg-navy-850 rounded animate-pulse" />
                <div className="h-16 bg-navy-850 rounded animate-pulse" />
                <div className="h-12 bg-navy-850 rounded animate-pulse" />
              </div>
            )}

            {preMarket && !preMarket.success && (
              <div className="p-3 bg-red-950/30 border border-red-800/40 text-red-300 rounded-lg text-center">
                <p className="font-bold mb-1">AI Not Ready</p>
                <p className="text-[10px] opacity-80">{preMarket.error}</p>
                <button
                  onClick={() => refetchPre()}
                  className="mt-2 px-2.5 py-1 bg-red-900/40 hover:bg-red-900/60 rounded text-[10px] font-bold border border-red-800 transition focus:outline-none"
                >
                  Retry
                </button>
              </div>
            )}

            {preMarket && preMarket.success && (
              <div className="space-y-2.5 font-mono">
                {/* Score and VIX Row */}
                <div className="flex items-center justify-between bg-navy-850 p-2 rounded-lg border border-navy-800">
                  <div>
                    <span className="text-navy-400 uppercase tracking-wide text-[9px] block">INDIA VIX</span>
                    <span className="text-sm font-bold text-white">{preMarket.vix?.toFixed(2)}%</span>
                  </div>
                  
                  <div className="text-right">
                    <span className="text-navy-400 uppercase tracking-wide text-[9px] block">Level Spacing Score</span>
                    <span className={clsx(
                      'text-sm font-extrabold',
                      (preMarket.quality_score ?? 0) >= 80 ? 'text-green-400' : (preMarket.quality_score ?? 0) >= 50 ? 'text-yellow-400' : 'text-red-400'
                    )}>
                      {preMarket.quality_score}/100
                    </span>
                  </div>
                </div>

                {/* Score Reason */}
                {preMarket.quality_reason && (
                  <p className="text-[10px] text-yellow-400 italic bg-yellow-950/20 border border-yellow-900/30 px-2 py-1.5 rounded">
                    Score Reason: {preMarket.quality_reason}
                  </p>
                )}

                {/* VIX Analysis */}
                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-blue-400 font-bold block mb-1">Vol Analysis</span>
                  {preMarket.vix_analysis}
                </div>

                {/* Expected Range */}
                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-blue-400 font-bold block mb-1">Expected Daily Range</span>
                  {preMarket.expected_range}
                </div>

                {/* Level Assessment */}
                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-blue-400 font-bold block mb-1">Current Level Quality</span>
                  {preMarket.level_assessment}
                </div>

                {/* Suggested configuration */}
                {preMarket.suggested_config && (
                  <div className="bg-navy-850 p-2 rounded-lg border border-navy-800/80">
                    <span className="text-blue-400 font-bold block mb-1.5 uppercase tracking-wide text-[9px]">Suggested Spacing Levels</span>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[10px]">
                      <div>
                        <span className="text-navy-400">CE Support (S1/S2/S3):</span>
                        <span className="block font-bold text-green-400">
                          {preMarket.suggested_config.s1} / {preMarket.suggested_config.s2} / {preMarket.suggested_config.s3}
                        </span>
                      </div>
                      <div>
                        <span className="text-navy-400">PE Resistance (R1/R2/R3):</span>
                        <span className="block font-bold text-red-400">
                          {preMarket.suggested_config.r1} / {preMarket.suggested_config.r2} / {preMarket.suggested_config.r3}
                        </span>
                      </div>
                    </div>
                    <span className="text-[8px] text-navy-400 mt-2 block italic text-center">AI advice remains Advisory — review before applying in Settings.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: POST-SESSION REVIEW */}
        {activeTab === 'post' && (
          <div className="space-y-2.5 text-[11px]">
            {isPostLoading && (
              <div className="space-y-2.5 py-2">
                <div className="h-16 bg-navy-850 rounded animate-pulse" />
                <div className="h-16 bg-navy-850 rounded animate-pulse" />
              </div>
            )}

            {postSession && !postSession.success && (
              <div className="p-3 bg-red-950/30 border border-red-800/40 text-red-300 rounded-lg text-center font-mono">
                <p className="font-bold mb-1">AI Not Ready</p>
                <p className="text-[10px] opacity-80">{postSession.error}</p>
                <button
                  onClick={() => refetchPost()}
                  className="mt-2 px-2.5 py-1 bg-red-900/40 hover:bg-red-900/60 rounded text-[10px] font-bold border border-red-800 transition focus:outline-none"
                >
                  Retry
                </button>
              </div>
            )}

            {postSession && postSession.success && (
              <div className="space-y-2.5 font-mono">
                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-green-400 font-bold block mb-1">What Worked</span>
                  {postSession.what_worked}
                </div>

                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-red-400 font-bold block mb-1">What Didn't Work</span>
                  {postSession.what_didnt_work}
                </div>

                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-orange-400 font-bold block mb-1">Volatility Patterns Observed</span>
                  {postSession.patterns_observed}
                </div>

                <div className="bg-navy-850/60 p-2.5 rounded border border-navy-800/60 leading-relaxed text-navy-200">
                  <span className="text-blue-400 font-bold block mb-1">Adjustments for Tomorrow</span>
                  {postSession.future_advice}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
