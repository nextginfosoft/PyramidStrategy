import { useState } from 'react'
import clsx from 'clsx'

export function UserGuide({ onClose }: { onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<'start' | 'features' | 'roadmap' | 'faq'>('start')

  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50 flex justify-end animate-fade-in"
      onClick={onClose}
    >
      <div 
        className="bg-navy-900 border-l border-navy-700/80 w-full max-w-md h-full shadow-2xl flex flex-col animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/60 backdrop-blur-md">
          <div className="flex items-center gap-2">
            <span className="text-base text-orange-400 font-bold font-mono tracking-wide uppercase">
              📖 Platform Help Guide
            </span>
          </div>
          <button 
            onClick={onClose}
            className="text-navy-300 hover:text-navy-100 hover:bg-navy-850 p-1.5 rounded-lg transition duration-150 focus:outline-none"
            aria-label="Close user guide"
          >
            ✕
          </button>
        </div>

        {/* Tab Buttons */}
        <div className="flex border-b border-navy-800 bg-navy-950/40 p-2 gap-1 overflow-x-auto scrollbar-thin">
          {(['start', 'features', 'roadmap', 'faq'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-2.5 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded transition-all focus:outline-none whitespace-nowrap',
                activeTab === tab
                  ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                  : 'text-navy-300 hover:text-navy-100 hover:bg-navy-850'
              )}
            >
              {tab === 'start' ? '🚀 Guide' : tab === 'features' ? '⚡ Features' : tab === 'roadmap' ? '🗺️ Roadmap' : '❓ FAQ'}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin text-navy-200 text-xs leading-relaxed font-mono">
          
          {/* TAB 1: GETTING STARTED */}
          {activeTab === 'start' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-orange-400 font-bold text-xs uppercase tracking-wider mb-2 border-b border-navy-800 pb-1">
                  1. Kite Session Login
                </h3>
                <p className="text-navy-300 mb-2">
                  Zerodha API credentials expire daily. Every morning before market open:
                </p>
                <ol className="list-decimal pl-4 space-y-1.5 text-navy-200">
                  <li>Find the <span className="text-white">Kite Status</span> card on the dashboard.</li>
                  <li>Click <span className="text-orange-400 hover:underline cursor-pointer">Login to Kite</span> to authenticate.</li>
                  <li>Once returned, verify status shows a green <span className="text-green-400">ACTIVE</span> ticker badge.</li>
                </ol>
              </div>

              <div>
                <h3 className="text-orange-400 font-bold text-xs uppercase tracking-wider mb-2 border-b border-navy-800 pb-1">
                  2. Pre-market Configuration
                </h3>
                <p className="text-navy-300 mb-2">
                  At 8:45 AM IST, the AI computes levels based on daily volatility.
                </p>
                <ul className="list-disc pl-4 space-y-1 text-navy-200">
                  <li>Go to the <span className="text-white">AI Observer</span>, open the <span className="text-blue-400">Pre-Market</span> tab.</li>
                  <li>Click <span className="text-orange-400 font-bold">Approve Suggested Config & Arm</span>.</li>
                  <li>This auto-populates R1-R3 / S1-S3 levels and boots the engine.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-orange-400 font-bold text-xs uppercase tracking-wider mb-2 border-b border-navy-800 pb-1">
                  3. Manual Configuration
                </h3>
                <p className="text-navy-300 mb-2">
                  If skipping AI recommendations, configure strategy parameters:
                </p>
                <ul className="list-disc pl-4 space-y-1.5 text-navy-200">
                  <li>Open <span className="text-white">Settings</span> &gt; <span className="text-white">Strategy Config</span>.</li>
                  <li>Enter CE Support spacing and PE Resistance spacing levels.</li>
                  <li>Choose your preferred mode: <span className="text-yellow-400">Paper Trade</span> or <span className="text-orange-400">Live Trade</span>.</li>
                  <li>Click Save and then hit <span className="text-green-400">START</span> in the header.</li>
                </ul>
              </div>

              <div className="bg-navy-950/40 p-2.5 rounded border border-navy-800 text-[11px]">
                <span className="text-yellow-500 font-bold block mb-1">💡 Pro-Tip (Simulation)</span>
                In Paper Trade mode, use the <span className="text-white">Simulate Tick</span> input card to manually inject NIFTY prices to verify triggers, averaging, and targets risk-free.
              </div>
            </div>
          )}

          {/* TAB 2: SUPPORTED FEATURES */}
          {activeTab === 'features' && (
            <div className="space-y-3.5">
              <div className="bg-navy-850/50 p-3 rounded-lg border border-navy-800 space-y-2">
                <span className="text-white font-bold block">🔺 Spacing Options Engine</span>
                <p className="text-navy-300 text-[11px]">
                  Runs automated intraday state machines targeting 20-point gains per leg. Leverages 3-level averaging limits (1:1:1 progression) and enforces a hard Level 3 stop boundary.
                </p>
              </div>

              <div className="bg-navy-850/50 p-3 rounded-lg border border-navy-800 space-y-2">
                <span className="text-blue-400 font-bold block">🤖 Multi-stage AI Observer</span>
                <p className="text-navy-300 text-[11px]">
                  Delivers advisory market intelligence. Includes live trade explanation logs, pre-market VIX/PCR/Max Pain snapshots, and EOD performance breakdowns.
                </p>
              </div>

              <div className="bg-navy-850/50 p-3 rounded-lg border border-navy-800 space-y-2">
                <span className="text-yellow-400 font-bold block">📋 Comprehensive PDF Reports</span>
                <p className="text-navy-300 text-[11px]">
                  Automatically builds and archives detailed execution summaries. Dispatches daily reports at 12:30 PM and weekly logs on Monday morning.
                </p>
              </div>

              <div className="bg-navy-850/50 p-3 rounded-lg border border-navy-800 space-y-2">
                <span className="text-green-400 font-bold block">🔔 Telegram Alerts</span>
                <p className="text-navy-300 text-[11px]">
                  Keeps you notified on your phone. Dispatches alerts for every position entry, target exit, stop-loss trigger, and error event.
                </p>
              </div>
            </div>
          )}

          {/* TAB 3: PLATFORM ROADMAP */}
          {activeTab === 'roadmap' && (
            <div className="space-y-4">
              <div className="relative border-l border-navy-800 pl-4 ml-1.5 space-y-4">
                
                {/* Milestone 1 */}
                <div className="relative">
                  <div className="absolute -left-[21px] top-0.5 bg-green-500 w-2.5 h-2.5 rounded-full border border-navy-950" />
                  <span className="text-green-400 font-bold block text-[11px]">PHASE 3: AI Observer & Telegram</span>
                  <span className="text-[10px] text-navy-400">Status: COMPLETED & ACTIVE</span>
                  <p className="text-navy-300 text-[11px] mt-1">
                    Multi-user DB briefs, automated schedulers, and Approve & Arm dashboard integration.
                  </p>
                </div>

                {/* Milestone 2 */}
                <div className="relative">
                  <div className="absolute -left-[21px] top-0.5 bg-orange-500 w-2.5 h-2.5 rounded-full border border-navy-950" />
                  <span className="text-orange-400 font-bold block text-[11px]">PHASE 4: BANKNIFTY Multi-Instrument</span>
                  <span className="text-[10px] text-navy-400">Status: IN PROGRESS</span>
                  <p className="text-navy-300 text-[11px] mt-1">
                    Supporting BANKNIFTY spot tracking, individual level panels, and separate metrics.
                  </p>
                </div>

                {/* Milestone 3 */}
                <div className="relative">
                  <div className="absolute -left-[21px] top-0.5 bg-navy-700 w-2.5 h-2.5 rounded-full border border-navy-950" />
                  <span className="text-navy-300 font-bold block text-[11px]">PHASE 5: Option Greeks & Greeks Panel</span>
                  <span className="text-[10px] text-navy-400">Status: PLANNED</span>
                  <p className="text-navy-300 text-[11px] mt-1">
                    Display Delta, Gamma, Theta decay, and IV percentile metrics for open positions.
                  </p>
                </div>

                {/* Milestone 4 */}
                <div className="relative">
                  <div className="absolute -left-[21px] top-0.5 bg-navy-700 w-2.5 h-2.5 rounded-full border border-navy-950" />
                  <span className="text-navy-300 font-bold block text-[11px]">PHASE 6: SaaS & Mobile App wrapping</span>
                  <span className="text-[10px] text-navy-400">Status: FUTURE MVP</span>
                  <p className="text-navy-300 text-[11px] mt-1">
                    Multi-tenant workspace, subscription billing, and Progressive Web App packaging.
                  </p>
                </div>

              </div>
            </div>
          )}

          {/* TAB 4: FAQ */}
          {activeTab === 'faq' && (
            <div className="space-y-4">
              <div className="space-y-1">
                <span className="text-orange-400 font-bold block">Q: How does the Stop Loss work?</span>
                <p className="text-navy-300 text-[11px]">
                  A: The 10-point stop loss is only applied to **Level 3**. If Level 1 or 2 entries fail to reach target, the strategy averages. A hard exit is only taken if the average price breaches the Level 3 stop limit.
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-orange-400 font-bold block">Q: Why did my simulated paper trade not trigger?</span>
                <p className="text-navy-300 text-[11px]">
                  A: Make sure you have clicked **START** in the top header. In addition, the engine enforces strict time filters (no new entries allowed after 11:15 AM).
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-orange-400 font-bold block">Q: What happens at 11:30 AM IST?</span>
                <p className="text-navy-300 text-[11px]">
                  A: The engine triggers a **Force Square-Off** on all active contracts. This closes all open positions automatically to avoid carrying overnight risk.
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-orange-400 font-bold block">Q: Does the AI auto-trade or configure levels?</span>
                <p className="text-navy-300 text-[11px]">
                  A: No. AI metrics and spacing recommendations are strictly advisory and require you to review and click **Approve** on the pre-market panel to update active values.
                </p>
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-4 border-t border-navy-800 bg-navy-950/20 text-center text-[10px] text-navy-400 font-mono italic">
          PyramidStrategy v1.0.0 — Enforcing Core Strategy Constraints.
        </div>
      </div>
    </div>
  )
}
