import React, { useState } from 'react'

interface Props {
  onLoginClick: () => void
  onRegisterClick: () => void
  onViewPricingClick: () => void
}

export function LandingPage({ onLoginClick, onRegisterClick, onViewPricingClick }: Props) {
  const [activeTab, setActiveTab] = useState<'monthly' | 'quarterly' | 'annual'>('quarterly')
  const [previewTab, setPreviewTab] = useState<'dashboard' | 'levels' | 'pnl' | 'telegram'>('dashboard')
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  const faqs = [
    {
      q: "How does DestinyAI execute option trades?",
      a: "DestinyAI connects to your Zerodha Kite Connect account via direct APIs and WebSocket live feeds. It constantly monitors NIFTY spot ticks against your configured Resistance (R1-R3) and Support (S1-S3) levels. When NIFTY crosses a level, the system automatically selects the corresponding ATM±50 option contract (same-day or next-weekly expiry) and submits market orders instantly."
    },
    {
      q: "Is Paper Trading completely free?",
      a: "Yes! The Basic plan offers 100% free, unlimited paper trading. DestinyAI simulates order execution using live tick quotes from the exchange, allowing you to test parameters, evaluate level accuracy, and review PnL reports without risking real capital."
    },
    {
      q: "How does the Dynamic Auto Square-off work?",
      a: "You can specify a custom end-of-day square-off time (such as 15:20 or 15:15 IST). DestinyAI automatically enforces an entry cutoff 15 minutes prior to your square-off time (no new positions entered) and closes all active open positions at your square-off time to protect you against sharp market closing spikes."
    },
    {
      q: "What is the Tuesday Expiry Rule?",
      a: "Because same-day option contracts on expiry days (like Tuesdays for NIFTY) suffer rapid theta decay and unpredictable spread spikes, DestinyAI automatically rolls over to the next weekly Thursday expiry contract on Tuesdays to protect your positions."
    },
    {
      q: "Do I need to keep my computer on during trading hours?",
      a: "No. DestinyAI runs as a server-side cloud background engine. Once you start the engine in the morning, it operates autonomously until square-off or until manually paused."
    }
  ]

  const [simLots, setSimLots] = useState(2)
  const [simTarget, setSimTarget] = useState(30)
  const [simWinRate, setSimWinRate] = useState(70)
  const [simTradesPerMonth, setSimTradesPerMonth] = useState(20)

  // Level Calculator Widget State
  const [calcSpot, setCalcSpot] = useState(24150)
  const calcR1 = Math.round(calcSpot + 50)
  const calcR2 = Math.round(calcSpot + 100)
  const calcR3 = Math.round(calcSpot + 150)
  const calcS1 = Math.round(calcSpot - 50)
  const calcS2 = Math.round(calcSpot - 100)
  const calcS3 = Math.round(calcSpot - 150)

  // Calculations based on NIFTY Lot Size = 65
  const lotQty = simLots * 65
  const profitPerWinTrade = lotQty * simTarget
  const lossPerLossTrade = lotQty * (simTarget * 0.8) // Assume risk-reward ratio 1:0.8
  const winTrades = Math.round((simTradesPerMonth * simWinRate) / 100)
  const lossTrades = simTradesPerMonth - winTrades
  const estGrossProfit = winTrades * profitPerWinTrade
  const estGrossLoss = lossTrades * lossPerLossTrade
  const estNetMonthlyPnL = estGrossProfit - estGrossLoss
  const [showDemoModal, setShowDemoModal] = useState(false)
  const [demoStep, setDemoStep] = useState(1)
  const [copied, setCopied] = useState(false)
  const [timeLeft, setTimeLeft] = useState({ hours: 4, minutes: 18, seconds: 45 })

  React.useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev.seconds > 0) return { ...prev, seconds: prev.seconds - 1 }
        if (prev.minutes > 0) return { ...prev, minutes: 59, seconds: 59 }
        if (prev.hours > 0) return { hours: prev.hours - 1, minutes: 59, seconds: 59 }
        return { hours: 5, minutes: 59, seconds: 59 } // reset
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const handleCopyCode = () => {
    navigator.clipboard.writeText('PRO15')
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Top Promotional Offer Announcement Bar with Live Countdown Timer & 1-Click Code Copy */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white text-xs font-bold py-2 px-4 text-center shadow-md sticky top-0 z-50 flex flex-wrap items-center justify-center gap-3">
        <span className="bg-white/20 text-white text-[10px] px-2.5 py-0.5 rounded-full uppercase tracking-widest font-extrabold animate-pulse">
          🔥 Flash Sale Ends In: {String(timeLeft.hours).padStart(2, '0')}:{String(timeLeft.minutes).padStart(2, '0')}:{String(timeLeft.seconds).padStart(2, '0')}
        </span>
        <span className="text-slate-100 text-xs">
          Get Up to <strong className="text-yellow-300">15% OFF</strong> Pro Subscriptions!
        </span>
        <button
          onClick={handleCopyCode}
          className="bg-slate-950/80 hover:bg-slate-950 text-yellow-300 border border-yellow-300/40 px-2.5 py-0.5 rounded-lg text-[11px] font-mono font-extrabold transition-all flex items-center gap-1.5 shadow"
        >
          <span>PRO15</span>
          <span className="text-[9px] bg-yellow-400 text-slate-950 px-1 py-0.2 rounded font-sans">
            {copied ? '✓ COPIED!' : 'COPY'}
          </span>
        </button>
        <button
          onClick={() => {
            const el = document.getElementById('pricing-section')
            if (el) el.scrollIntoView({ behavior: 'smooth' })
            else onViewPricingClick()
          }}
          className="bg-yellow-400 hover:bg-yellow-300 text-slate-950 font-extrabold px-3 py-1 rounded-full text-[11px] transition-transform hover:scale-105 shrink-0 shadow"
        >
          Claim Offer →
        </button>
      </div>

      {/* Navigation Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-[36px] z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center text-white font-extrabold text-lg shadow-lg shadow-indigo-500/25">
              D
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Destiny<span className="text-indigo-400">AI</span>
            </span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={onLoginClick}
              className="text-sm font-semibold text-slate-300 hover:text-white transition-colors px-3 py-1.5"
            >
              Log In
            </button>
            <button
              onClick={onRegisterClick}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-all shadow-md shadow-indigo-600/20 hover:shadow-indigo-600/40"
            >
              Get Started Free
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-20 pb-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center flex-1">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-6 animate-pulse">
          🚀 Next-Gen Automated NIFTY Options Trading Platform
        </div>
        <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight max-w-4xl mx-auto">
          Automate Level-Based <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400">Options Trading</span> with DestinyAI
        </h1>
        <p className="mt-6 text-lg sm:text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed">
          Execute NIFTY Support & Resistance level-based option strategies automatically with live broker integration (Zerodha Kite), dynamic auto square-off rules, risk management, and risk-free paper trading.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={onRegisterClick}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-base px-8 py-3.5 rounded-2xl transition-all shadow-lg shadow-indigo-600/30 hover:scale-105"
          >
            Start Free Paper Trading
          </button>
          <button
            onClick={() => {
              const el = document.getElementById('pricing-section')
              if (el) el.scrollIntoView({ behavior: 'smooth' })
              else onViewPricingClick()
            }}
            className="bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-semibold text-base px-8 py-3.5 rounded-2xl transition-all"
          >
            View Pro Pricing Plans
          </button>
          <button
            onClick={() => {
              setShowDemoModal(true)
              setDemoStep(1)
            }}
            className="bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 font-semibold text-base px-6 py-3.5 rounded-2xl transition-all flex items-center gap-2"
          >
            <span className="w-6 h-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold shadow">▶</span>
            <span>Watch 60-Sec Demo</span>
          </button>
        </div>

        {/* Interactive App UI Preview Carousel */}
        <div className="mt-16 relative mx-auto max-w-5xl rounded-3xl border border-slate-800 bg-slate-900/80 p-4 sm:p-6 shadow-2xl backdrop-blur-xl">
          {/* Top Browser Bar & Tabs */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-b border-slate-800 pb-4 mb-6">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-amber-500/80" />
              <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="text-xs text-slate-400 ml-2 font-mono font-bold">DestinyAI App Preview</span>
            </div>

            {/* Interactive Selector Tabs */}
            <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
              <button
                onClick={() => setPreviewTab('dashboard')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  previewTab === 'dashboard'
                    ? 'bg-indigo-600 text-white font-bold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                📊 Dashboard View
              </button>
              <button
                onClick={() => setPreviewTab('levels')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  previewTab === 'levels'
                    ? 'bg-indigo-600 text-white font-bold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                🎯 Level Setup
              </button>
              <button
                onClick={() => setPreviewTab('pnl')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  previewTab === 'pnl'
                    ? 'bg-indigo-600 text-white font-bold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                📈 Live PnL Chart
              </button>
              <button
                onClick={() => setPreviewTab('telegram')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  previewTab === 'telegram'
                    ? 'bg-indigo-600 text-white font-bold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                🔔 Telegram Alerts
              </button>
            </div>
          </div>

          {/* Dynamic Tab Content Box */}
          <div className="bg-slate-950 rounded-2xl p-6 border border-slate-800/80 text-left transition-all">
            {previewTab === 'dashboard' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 p-5 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 font-medium">NIFTY Spot Ticker</span>
                  <p className="text-3xl font-extrabold text-emerald-400 mt-1 font-mono">24,185.50</p>
                  <span className="text-[10px] text-emerald-400 font-semibold">▲ +120.35 (+0.50%) IST</span>
                </div>
                <div className="bg-slate-900 p-5 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 font-medium">Zerodha Broker Connection</span>
                  <p className="text-2xl font-bold text-indigo-400 mt-1">Live Feed Active</p>
                  <span className="text-[10px] text-slate-400">WebSocket Sub-Second Ticks</span>
                </div>
                <div className="bg-slate-900 p-5 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 font-medium">Today's Net Realized PnL</span>
                  <p className="text-3xl font-extrabold text-emerald-400 mt-1 font-mono">+₹4,550</p>
                  <span className="text-[10px] text-slate-400">2 Trades | 100% Win Rate</span>
                </div>
              </div>
            )}

            {previewTab === 'levels' && (
              <div className="space-y-4">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Resistance & Support Level Config</h4>
                  <span className="text-[10px] bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded font-mono">PYRAMID ENGINE</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs font-mono">
                  <div className="bg-slate-900 p-3 rounded-xl border border-red-500/30">
                    <span className="text-red-400 font-bold block">R1 Level (PE Trigger)</span>
                    <span className="text-lg text-white font-extrabold">24,250</span>
                  </div>
                  <div className="bg-slate-900 p-3 rounded-xl border border-red-500/30">
                    <span className="text-red-400 font-bold block">R2 Level (PE Scale)</span>
                    <span className="text-lg text-white font-extrabold">24,300</span>
                  </div>
                  <div className="bg-slate-900 p-3 rounded-xl border border-emerald-500/30">
                    <span className="text-emerald-400 font-bold block">S1 Level (CE Trigger)</span>
                    <span className="text-lg text-white font-extrabold">24,100</span>
                  </div>
                </div>
              </div>
            )}

            {previewTab === 'pnl' && (
              <div className="space-y-4">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Intraday PnL Growth Curve</h4>
                  <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-bold">+₹4,550 Peak</span>
                </div>
                <div className="h-32 bg-slate-900 rounded-xl border border-slate-800 flex items-end justify-between p-4 gap-2">
                  <div className="w-1/6 bg-indigo-500/20 h-1/4 rounded-t" />
                  <div className="w-1/6 bg-indigo-500/40 h-2/4 rounded-t" />
                  <div className="w-1/6 bg-emerald-500/60 h-3/4 rounded-t" />
                  <div className="w-1/6 bg-emerald-500/80 h-4/5 rounded-t" />
                  <div className="w-1/6 bg-emerald-500 h-full rounded-t animate-pulse" />
                </div>
              </div>
            )}

            {previewTab === 'telegram' && (
              <div className="space-y-3">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Telegram Bot Push Alerts</h4>
                  <span className="text-[10px] bg-sky-500/20 text-sky-400 px-2 py-0.5 rounded font-bold">INSTANT PUSH</span>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-3 rounded-xl font-mono text-xs text-sky-300">
                  ⚡ <strong>[DESTINY AI ALERT]</strong>: NIFTY 24,100 Support Crossed! Entered 1 Lot NIFTY 24,100 CE @ ₹120.00. Target: +30 pts | SL: 30 pts.
                </div>
                <div className="bg-slate-900 border border-slate-800 p-3 rounded-xl font-mono text-xs text-emerald-300">
                  🎯 <strong>[TARGET HIT]</strong>: Exited 1 Lot NIFTY 24,100 CE @ ₹150.00 (+30 pts Profit). Gross Trade PnL: +₹1,950!
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* How DestinyAI Works Section */}
      <section className="py-20 bg-slate-900/60 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/20">
              Simple 4-Step Workflow
            </span>
            <h2 className="text-3xl font-extrabold text-white mt-4">How DestinyAI Automates Your Trading</h2>
            <p className="text-slate-400 text-sm mt-2 max-w-xl mx-auto">From morning pre-market level setup to automated execution and daily PDF reporting.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="bg-slate-950 border border-slate-800 p-6 rounded-2xl relative">
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-extrabold text-sm flex items-center justify-center mb-4">
                1
              </div>
              <h3 className="text-base font-bold text-white mb-2">Pre-Market Setup</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Set your custom Resistance (R1-R3) and Support (S1-S3) levels pre-market, or use AI-assisted pivot recommendations.
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 p-6 rounded-2xl relative">
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-extrabold text-sm flex items-center justify-center mb-4">
                2
              </div>
              <h3 className="text-base font-bold text-white mb-2">Live Market Ticker</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                DestinyAI connects via Zerodha WebSocket API to monitor real-time NIFTY spot ticks continuously without UI lag.
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 p-6 rounded-2xl relative">
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-extrabold text-sm flex items-center justify-center mb-4">
                3
              </div>
              <h3 className="text-base font-bold text-white mb-2">Automated Execution</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Upon level crossover, the engine selects ATM±50 PE/CE options, executes market orders, and tracks Target (+30 pts) & SL (30 pts).
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 p-6 rounded-2xl relative">
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white font-extrabold text-sm flex items-center justify-center mb-4">
                4
              </div>
              <h3 className="text-base font-bold text-white mb-2">Daily Reports & Alerts</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Get instant Telegram alerts for every trade event and automated daily/weekly PDF trading reports sent directly to your inbox.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Strategy & PnL Simulator Section */}
      <section className="py-20 bg-slate-950 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
              Interactive Returns Simulator
            </span>
            <h2 className="text-3xl font-extrabold text-white mt-4">Simulate Your Monthly Returns</h2>
            <p className="text-slate-400 text-sm mt-2 max-w-xl mx-auto">
              Adjust parameters below to estimate potential monthly returns based on your lot sizing and target strategy rules.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-10 shadow-2xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Input Controls Column */}
            <div className="lg:col-span-7 space-y-6">
              {/* Slider 1: Lots */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Trading Lot Size</label>
                  <span className="text-sm font-extrabold text-indigo-400">{simLots} Lots ({lotQty} Shares)</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="1"
                  value={simLots}
                  onChange={e => setSimLots(+e.target.value)}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>1 Lot (65)</span>
                  <span>5 Lots (325)</span>
                  <span>10 Lots (650)</span>
                </div>
              </div>

              {/* Slider 2: Target Points */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Target Points per Trade</label>
                  <span className="text-sm font-extrabold text-emerald-400">+{simTarget} Pts</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="50"
                  step="5"
                  value={simTarget}
                  onChange={e => setSimTarget(+e.target.value)}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>+15 Pts</span>
                  <span>+30 Pts</span>
                  <span>+50 Pts</span>
                </div>
              </div>

              {/* Slider 3: Win Rate */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Assumed Strategy Win Rate</label>
                  <span className="text-sm font-extrabold text-amber-400">{simWinRate}%</span>
                </div>
                <input
                  type="range"
                  min="50"
                  max="90"
                  step="5"
                  value={simWinRate}
                  onChange={e => setSimWinRate(+e.target.value)}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>50%</span>
                  <span>70%</span>
                  <span>90%</span>
                </div>
              </div>

              {/* Slider 4: Monthly Trades */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Est. Level Triggers per Month</label>
                  <span className="text-sm font-extrabold text-purple-400">{simTradesPerMonth} Trades</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="40"
                  step="5"
                  value={simTradesPerMonth}
                  onChange={e => setSimTradesPerMonth(+e.target.value)}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>10 Trades</span>
                  <span>20 Trades</span>
                  <span>40 Trades</span>
                </div>
              </div>
            </div>

            {/* Results Card Column */}
            <div className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between h-full shadow-inner">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-bold tracking-widest block mb-1">Simulated Monthly Net Return</span>
                <div className="my-4">
                  <span className={`text-4xl font-extrabold ${estNetMonthlyPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {estNetMonthlyPnL >= 0 ? '+' : ''}₹{estNetMonthlyPnL.toLocaleString('en-IN')}
                  </span>
                  <span className="text-xs text-slate-400 block mt-1">Estimated Net Intraday Option PnL</span>
                </div>

                <div className="space-y-2.5 pt-4 border-t border-slate-800 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Winning Trades ({winTrades}):</span>
                    <span className="text-emerald-400 font-bold">+₹{estGrossProfit.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Losing Trades ({lossTrades}):</span>
                    <span className="text-red-400 font-bold">-₹{estGrossLoss.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Profit per Winning Trade:</span>
                    <span className="text-slate-200">+₹{profitPerWinTrade.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-800/80">
                <button
                  onClick={onRegisterClick}
                  className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/30 hover:scale-[1.02]"
                >
                  Test Strategy in Free Paper Trading →
                </button>
                <span className="text-[10px] text-slate-500 text-center block mt-2">
                  *Simulation for illustrative purposes. Past performance is not guaranteed investment advice.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pre-Market NIFTY Level Calculator Widget Section */}
      <section className="py-16 bg-slate-900/60 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/20">
            Instant Level Calculator
          </span>
          <h2 className="text-3xl font-extrabold text-white mt-4">Try Your Pre-Market NIFTY Levels</h2>
          <p className="text-slate-400 text-sm mt-2 max-w-lg mx-auto">
            Type an estimated NIFTY Spot Price to preview calculated Support (CE) & Resistance (PE) trigger bands.
          </p>

          <div className="mt-8 bg-slate-950 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl text-left">
            <div className="max-w-md mx-auto mb-8">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2 text-center">
                Enter NIFTY Spot Index Price
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="10"
                  value={calcSpot}
                  onChange={e => setCalcSpot(+e.target.value || 24000)}
                  className="w-full bg-slate-900 border border-indigo-500/50 rounded-2xl px-4 py-3 text-center text-xl font-bold text-white font-mono focus:border-indigo-400 focus:outline-none shadow-inner"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-500 font-mono">
                  NIFTY 50
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Resistance Levels */}
              <div className="bg-slate-900 border border-red-500/20 rounded-2xl p-5 space-y-3">
                <h4 className="text-xs font-extrabold text-red-400 uppercase tracking-wider border-b border-red-500/20 pb-2 flex items-center gap-2">
                  <span>🔴 Resistance Levels (PE Triggers)</span>
                </h4>
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">R1 Level:</span>
                    <span className="text-white font-bold">{calcR1.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">R2 Level:</span>
                    <span className="text-white font-bold">{calcR2.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">R3 Level:</span>
                    <span className="text-white font-bold">{calcR3.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>

              {/* Support Levels */}
              <div className="bg-slate-900 border border-emerald-500/20 rounded-2xl p-5 space-y-3">
                <h4 className="text-xs font-extrabold text-emerald-400 uppercase tracking-wider border-b border-emerald-500/20 pb-2 flex items-center gap-2">
                  <span>🟢 Support Levels (CE Triggers)</span>
                </h4>
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">S1 Level:</span>
                    <span className="text-white font-bold">{calcS1.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">S2 Level:</span>
                    <span className="text-white font-bold">{calcS2.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">S3 Level:</span>
                    <span className="text-white font-bold">{calcS3.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights Grid */}
      <section className="py-20 border-t border-slate-800/60 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white">Built for Systematic Options Traders</h2>
          <p className="text-slate-400 text-sm mt-2">Eliminate emotional bias with automated, rule-driven execution and strict risk controls.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-indigo-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-xl mb-4">
              📊
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Automated Level Crossover Engine</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Define pre-market Resistance (R1-R3) and Support (S1-S3) levels. DestinyAI automatically monitors NIFTY spot ticks and triggers PE/CE orders upon exact level crossovers.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-amber-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold text-xl mb-4">
              ⏰
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Dynamic Auto Square-Off Settings</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Configure custom end-of-day square-off times (e.g. 15:15 or 15:20 IST) with an automatic 15-minute prior entry cutoff to prevent late market volatility exposure.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-emerald-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-xl mb-4">
              🛡️
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Risk-Free Paper Trading</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Simulate your strategy on live tick data without real capital risk. Fine-tune your target points, stop loss, and level parameters before going live.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-purple-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold text-xl mb-4">
              ⚡
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Zerodha Kite Direct API</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Pro plan users execute live trades directly into Zerodha Kite accounts with automated order status updates, WebSocket streaming, and audit trails.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-pink-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-pink-500/10 text-pink-400 flex items-center justify-center font-bold text-xl mb-4">
              📈
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Detailed Analytics & Reports</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Track win rates, PnL curve graphs, trade history logs, and download PDF daily/weekly trading activity reports for performance analysis.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl hover:border-blue-500/50 transition-colors">
            <div className="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold text-xl mb-4">
              🔔
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Instant Telegram & AI Alerts</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Receive instant Telegram push notifications for every trade entry, target exit, stop loss hit, and daily market performance summaries.
            </p>
          </div>
        </div>
      </section>

      {/* Safety & Risk Controls Highlight Section */}
      <section className="py-16 bg-slate-900/40 border-y border-slate-800/60 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div>
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
              Institutional Risk Controls
            </span>
            <h2 className="text-3xl font-extrabold text-white mt-4">Strict Risk Management Built In</h2>
            <p className="text-slate-400 text-sm mt-3 leading-relaxed">
              DestinyAI enforces automated circuit breaker rules so you never over-trade or suffer catastrophic drawdowns.
            </p>
            <ul className="mt-6 space-y-3 text-xs text-slate-300">
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                <div>
                  <strong className="text-white">Strict Target & Stop-Loss:</strong> Automatic exit triggers when option PnL hits target (+30 pts) or stop-loss (30 pts).
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                <div>
                  <strong className="text-white">Level-Lock Protection:</strong> Once a level target/SL is hit, that specific level is locked for the remainder of the session to prevent re-entry loops.
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                <div>
                  <strong className="text-white">Tuesday Expiry Exemption:</strong> Automatically uses next weekly expiry on Tuesdays to protect against intraday theta decay.
                </div>
              </li>
            </ul>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">
              System Audit & Risk Parameters
            </h3>
            <div className="space-y-4 text-xs font-mono">
              <div className="flex justify-between items-center bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400">Max Lots per Order</span>
                <span className="text-white font-bold">1 Lot (65 Shares)</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400">Market Entry Order Type</span>
                <span className="text-indigo-400 font-bold">Sub-Second MARKET</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400">Square-Off Protection</span>
                <span className="text-amber-400 font-bold">Dynamic Time Cutoff</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-400">API Credentials Security</span>
                <span className="text-emerald-400 font-bold">AES-256 Encrypted</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof & Live Platform Metrics Section */}
      <section className="py-20 bg-slate-950 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Live Metrics Counter Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center mb-20 bg-slate-900/60 border border-slate-800 p-8 rounded-3xl backdrop-blur-xl">
            <div>
              <p className="text-3xl sm:text-4xl font-extrabold text-white">500+</p>
              <p className="text-xs text-slate-400 font-medium mt-1">Active NIFTY Traders</p>
            </div>
            <div>
              <p className="text-3xl sm:text-4xl font-extrabold text-emerald-400">₹2.4 Cr+</p>
              <p className="text-xs text-slate-400 font-medium mt-1">Paper Volume Simulated</p>
            </div>
            <div>
              <p className="text-3xl sm:text-4xl font-extrabold text-indigo-400">&lt; 50ms</p>
              <p className="text-xs text-slate-400 font-medium mt-1">Average Order Latency</p>
            </div>
            <div>
              <p className="text-3xl sm:text-4xl font-extrabold text-amber-400">99.9%</p>
              <p className="text-xs text-slate-400 font-medium mt-1">WebSocket Feed Uptime</p>
            </div>
          </div>

          {/* Testimonials Header */}
          <div className="text-center mb-12">
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/20">
              Trader Feedback
            </span>
            <h2 className="text-3xl font-extrabold text-white mt-4">Trusted by Intraday Traders</h2>
            <p className="text-slate-400 text-sm mt-2 max-w-xl mx-auto">
              Here is what systematic options traders say about trading with DestinyAI level automation.
            </p>
          </div>

          {/* Testimonials Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col justify-between hover:border-indigo-500/40 transition-colors">
              <div>
                <div className="flex items-center gap-1 text-amber-400 text-sm mb-3">
                  ★★★★★
                </div>
                <p className="text-xs text-slate-300 leading-relaxed italic">
                  "DestinyAI completely removed emotional panic from my NIFTY trading. My levels trigger automatically, targets hit smoothly, and the Tuesday expiry rollover rule saved me from theta decay!"
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-indigo-600 text-white font-bold text-sm flex items-center justify-center">
                  RK
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Rajesh K.</h4>
                  <span className="text-[10px] text-slate-500">Pro Trader (Bengaluru)</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col justify-between hover:border-emerald-500/40 transition-colors">
              <div>
                <div className="flex items-center gap-1 text-amber-400 text-sm mb-3">
                  ★★★★★
                </div>
                <p className="text-xs text-slate-300 leading-relaxed italic">
                  "The paper trading mode is a game-changer. I tested my support-resistance levels for two weeks risk-free before deploying live funds with my Zerodha account."
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-emerald-600 text-white font-bold text-sm flex items-center justify-center">
                  PS
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Pooja Sharma</h4>
                  <span className="text-[10px] text-slate-500">Options Scalper (Mumbai)</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col justify-between hover:border-amber-500/40 transition-colors">
              <div>
                <div className="flex items-center gap-1 text-amber-400 text-sm mb-3">
                  ★★★★★
                </div>
                <p className="text-xs text-slate-300 leading-relaxed italic">
                  "The dynamic auto square-off feature gives total peace of mind. I set my cutoff to 15:20 IST, and all my positions close cleanly before market close spikes."
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-amber-600 text-white font-bold text-sm flex items-center justify-center">
                  VM
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Vikram Mehta</h4>
                  <span className="text-[10px] text-slate-500">Systematic Trader (Delhi)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Paper Trading vs Live Trading Detailed Comparison Section */}
      <section className="py-20 bg-slate-900/40 border-t border-slate-800/60 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
              Side-by-Side Comparison
            </span>
            <h2 className="text-3xl font-extrabold text-white mt-4">Paper Trading vs. Live Broker Trading</h2>
            <p className="text-slate-400 text-sm mt-2 max-w-xl mx-auto">
              Start risk-free with simulated paper execution. Upgrade to Pro whenever you are ready to send live orders directly to your Zerodha account.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-bold uppercase tracking-wider">
                    <th className="p-4 sm:p-5">Platform Capabilities</th>
                    <th className="p-4 sm:p-5 text-center bg-slate-900/60 text-slate-300 w-1/3">
                      Basic Plan (Paper Trading)
                    </th>
                    <th className="p-4 sm:p-5 text-center bg-indigo-950/40 text-indigo-400 w-1/3 border-l border-slate-800">
                      Pro Plan (Live Trading)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Capital Risk</td>
                    <td className="p-4 sm:p-5 text-center font-bold text-emerald-400">Zero Risk (₹0)</td>
                    <td className="p-4 sm:p-5 text-center font-bold text-amber-400 border-l border-slate-800">Live Capital on Broker</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Live Market Ticker Feed</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold">✓ WebSocket Live Spot</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ WebSocket Live Spot</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Level Crossover Automation</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold">✓ Automatic Triggers</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ Automatic Triggers</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Order Execution Engine</td>
                    <td className="p-4 sm:p-5 text-center text-slate-400">Local Simulation against LTP</td>
                    <td className="p-4 sm:p-5 text-center text-indigo-400 font-bold border-l border-slate-800">Direct Zerodha Kite API</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Dynamic Auto Square-Off (Smart Exit)</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold">✓ Included</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ Included</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Tuesday Expiry Protection Rule</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold">✓ Included</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ Included</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Telegram Push Notifications</td>
                    <td className="p-4 sm:p-5 text-center text-slate-500">✕ Disabled</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ Instant Live Alerts</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 font-semibold text-white">Daily PDF Trading Reports</td>
                    <td className="p-4 sm:p-5 text-center text-slate-500">✕ Standard Logs Only</td>
                    <td className="p-4 sm:p-5 text-center text-emerald-400 font-bold border-l border-slate-800">✓ Exportable PDF Summary</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing-section" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-extrabold text-white">Transparent & Flexible Pricing</h2>
          <p className="text-slate-400 text-sm mt-2">Start free with Paper Trading. Upgrade to Pro for Live Broker Execution.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Basic Plan */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
              <h3 className="text-lg font-bold text-white">Basic (Free)</h3>
              <p className="text-xs text-slate-400 mt-1">Perfect for testing and strategy validation.</p>
              <div className="my-6">
                <span className="text-3xl font-extrabold text-white">₹0</span>
                <span className="text-xs text-slate-400"> / forever</span>
              </div>
              <ul className="space-y-2 text-xs text-slate-300 mb-6">
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Unlimited Paper Trading</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Custom Level Config & Square-Off</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Trade Logs & PnL Analytics</li>
                <li className="flex items-center gap-2 text-slate-500"><span className="text-slate-600 font-bold">✕</span> Live Broker Execution</li>
              </ul>
            </div>
            <button
              onClick={onRegisterClick}
              className="w-full py-3 rounded-xl border border-indigo-500 text-indigo-400 hover:bg-indigo-500/10 font-bold text-xs transition-colors"
            >
              Get Started Free
            </button>
          </div>

          {/* Pro Monthly */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between">
            <div>
              <h3 className="text-lg font-bold text-white">Pro Monthly</h3>
              <p className="text-xs text-slate-400 mt-1">Monthly access for active live traders.</p>
              <div className="my-6">
                <span className="text-3xl font-extrabold text-white">₹4,999</span>
                <span className="text-xs text-slate-400"> / month</span>
              </div>
              <ul className="space-y-2 text-xs text-slate-300 mb-6">
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Everything in Basic</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Live Broker Execution (Zerodha)</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Telegram Alerts & AI Summaries</li>
              </ul>
            </div>
            <button
              onClick={onViewPricingClick}
              className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors"
            >
              Subscribe Monthly
            </button>
          </div>

          {/* Pro Quarterly */}
          <div className="bg-slate-800/90 border-2 border-indigo-500 rounded-2xl p-6 flex flex-col justify-between relative shadow-lg shadow-indigo-500/20 scale-[1.03]">
            <div className="absolute -top-3 right-4 bg-emerald-500 text-slate-950 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              10% OFF
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Pro Quarterly</h3>
              <p className="text-xs text-slate-400 mt-1">90-day discounted billing cycle.</p>
              <div className="my-6">
                <span className="text-3xl font-extrabold text-white">₹13,497</span>
                <span className="text-xs text-slate-400"> / 3 mos</span>
                <p className="text-[11px] text-emerald-400 font-medium mt-1">Effective ~₹4,499/month (Save ₹1,500)</p>
              </div>
              <ul className="space-y-2 text-xs text-slate-300 mb-6">
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Everything in Pro Monthly</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Priority Customer Support</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Backtest & PDF Report Export</li>
              </ul>
            </div>
            <button
              onClick={onViewPricingClick}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors shadow-md shadow-indigo-600/30"
            >
              Subscribe Quarterly
            </button>
          </div>

          {/* Pro Annual */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between relative">
            <div className="absolute -top-3 right-4 bg-emerald-500 text-slate-950 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              15% OFF
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Pro Annual</h3>
              <p className="text-xs text-slate-400 mt-1">Maximum savings for long-term systematic traders.</p>
              <div className="my-6">
                <span className="text-3xl font-extrabold text-white">₹50,989</span>
                <span className="text-xs text-slate-400"> / year</span>
                <p className="text-[11px] text-emerald-400 font-medium mt-1">Effective ~₹4,249/month (Save ₹8,999)</p>
              </div>
              <ul className="space-y-2 text-xs text-slate-300 mb-6">
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Full 365-Day Live Trading Access</li>
                <li className="flex items-center gap-2"><span className="text-emerald-400 font-bold">✓</span> Strategy & Level Setup Assistance</li>
              </ul>
            </div>
            <button
              onClick={onViewPricingClick}
              className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors"
            >
              Subscribe Annual
            </button>
          </div>
        </div>
      </section>

      {/* Frequently Asked Questions (FAQ) Section */}
      <section className="py-20 bg-slate-900/50 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-extrabold text-white">Frequently Asked Questions</h2>
          <p className="text-slate-400 text-sm mt-2">Everything you need to know about DestinyAI.</p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, idx) => (
            <div key={idx} className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <button
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                className="w-full p-5 text-left flex justify-between items-center text-sm font-bold text-white hover:bg-slate-800/50 transition-colors"
              >
                <span>{faq.q}</span>
                <span className="text-indigo-400 text-lg">{openFaq === idx ? '−' : '+'}</span>
              </button>
              {openFaq === idx && (
                <div className="px-5 pb-5 text-xs text-slate-400 leading-relaxed border-t border-slate-800/60 pt-3">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Trust Badges, Data Security Seals & Regulatory Compliance Section */}
      <section className="py-16 bg-slate-950 border-t border-slate-800/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Security & Trust Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 text-left mb-12">
            <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-xl shrink-0 font-bold">
                🔒
              </div>
              <div>
                <h4 className="text-xs font-bold text-white mb-1">AES-256 Key Encryption</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Your Zerodha API keys and secrets are encrypted at rest with military-grade AES-256 storage.
                </p>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center text-xl shrink-0 font-bold">
                🛡️
              </div>
              <div>
                <h4 className="text-xs font-bold text-white mb-1">Zero Capital Touch</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Your funds remain 100% safe inside your own Zerodha account. DestinyAI never holds user funds.
                </p>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center text-xl shrink-0 font-bold">
                ⚡
              </div>
              <div>
                <h4 className="text-xs font-bold text-white mb-1">Direct Kite Connect API</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Official WebSocket feed and direct REST endpoint integration for official exchange execution.
                </p>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center text-xl shrink-0 font-bold">
                ⚖️
              </div>
              <div>
                <h4 className="text-xs font-bold text-white mb-1">Strict Risk Management</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Automated circuit breakers, Tuesday expiry protection rules, and smart square-off time cutoffs.
                </p>
              </div>
            </div>
          </div>

          {/* SEBI Compliance & Risk Disclaimer Banner */}
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 text-slate-400 text-[11px] leading-relaxed">
            <div className="flex items-center gap-2 mb-2 text-slate-300 font-bold text-xs uppercase tracking-wider">
              <span>⚠️ Important Regulatory & Financial Risk Disclaimer</span>
            </div>
            <p>
              <strong>DestinyAI</strong> is an automated algorithmic trade execution tool designed for systematic NIFTY options traders. DestinyAI is <strong>not a SEBI-registered investment advisor, research analyst, or portfolio manager</strong>. The platform provides automated rule-based order placement tools based strictly on user-defined technical support and resistance levels. All information, simulations, and paper trading reports provided on this platform are for educational and strategy validation purposes only and should not be construed as investment or trading advice. Trading in derivatives (futures & options) involves substantial financial risk of loss. Ensure you fully understand market risks before deploying live capital.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-8 px-4 sm:px-6 lg:px-8 text-xs text-slate-500 mt-auto pb-20 sm:pb-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} DestinyAI. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <a href="#terms" className="hover:text-slate-400">Terms of Service</a>
            <a href="#privacy" className="hover:text-slate-400">Privacy Policy</a>
            <a href="#refund" className="hover:text-slate-400">Refund Policy</a>
            <a href="mailto:nextginfosoft@gmail.com" className="hover:text-slate-400">Support</a>
          </div>
        </div>
      </footer>

      {/* Floating Bottom-Right "Start Free Paper Trading" CTA Pill */}
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={onRegisterClick}
          className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-extrabold text-xs px-5 py-3 rounded-full shadow-2xl shadow-indigo-500/50 border border-indigo-400/30 flex items-center gap-2.5 transition-transform hover:scale-105 active:scale-95 animate-bounce"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>🚀 Start Free Paper Trading</span>
        </button>
      </div>

      {/* 60-Second Strategy Workflow Demo Lightbox Modal */}
      {showDemoModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-6 shadow-2xl relative overflow-hidden text-left">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎥</span>
                <h3 className="text-base font-bold text-white">60-Second DestinyAI Automated Trading Demo</h3>
              </div>
              <button
                onClick={() => setShowDemoModal(false)}
                className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center font-bold text-sm transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Interactive Timeline Step Progress Bar */}
            <div className="grid grid-cols-4 gap-2 mb-6">
              <button
                onClick={() => setDemoStep(1)}
                className={`py-2 px-3 rounded-xl text-[11px] font-bold transition-all text-center border ${
                  demoStep === 1
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                1. Level Setup
              </button>
              <button
                onClick={() => setDemoStep(2)}
                className={`py-2 px-3 rounded-xl text-[11px] font-bold transition-all text-center border ${
                  demoStep === 2
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                2. Spot Crossover
              </button>
              <button
                onClick={() => setDemoStep(3)}
                className={`py-2 px-3 rounded-xl text-[11px] font-bold transition-all text-center border ${
                  demoStep === 3
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                3. Market Order
              </button>
              <button
                onClick={() => setDemoStep(4)}
                className={`py-2 px-3 rounded-xl text-[11px] font-bold transition-all text-center border ${
                  demoStep === 4
                    ? 'bg-indigo-600 border-indigo-500 text-white shadow'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                4. Target Exit & PnL
              </button>
            </div>

            {/* Simulated Live Workflow Screen Container */}
            <div className="bg-slate-950 rounded-2xl border border-slate-800 p-6 min-h-[240px] flex flex-col justify-between font-mono text-xs">
              {demoStep === 1 && (
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest block">Step 01 / Morning Pre-Market Config</span>
                  <h4 className="text-sm font-bold text-white">1. Defining Support & Resistance Levels</h4>
                  <p className="text-slate-400 text-xs font-sans leading-relaxed">
                    At 9:00 AM IST, the trader sets Support level S1 at <strong>24,100</strong> and Resistance level R1 at <strong>24,250</strong>. Engine arms status turns <span className="text-emerald-400">READY</span>.
                  </p>
                  <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-slate-500 block text-[10px]">Support S1 (CE Entry)</span>
                      <span className="text-emerald-400 font-bold text-base">24,100</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">Resistance R1 (PE Entry)</span>
                      <span className="text-red-400 font-bold text-base">24,250</span>
                    </div>
                  </div>
                </div>
              )}

              {demoStep === 2 && (
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-widest block">Step 02 / Live WebSocket Tick Stream</span>
                  <h4 className="text-sm font-bold text-white">2. NIFTY Spot Crosses Level Signal</h4>
                  <p className="text-slate-400 text-xs font-sans leading-relaxed">
                    At 10:15 AM IST, NIFTY spot ticks from 24,098 up to <strong>24,101.50</strong>, crossing S1 (24,100). Level detector triggers instant signal debounced over WebSocket.
                  </p>
                  <div className="bg-slate-900 p-3 rounded-xl border border-amber-500/30 flex items-center justify-between">
                    <div>
                      <span className="text-slate-400 text-[10px]">WebSocket NIFTY Ticker</span>
                      <p className="text-white font-extrabold text-sm">24,101.50 ▲ (+1.50 pts)</p>
                    </div>
                    <span className="bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded font-bold text-[10px] animate-pulse">
                      CROSSOVER DETECTED
                    </span>
                  </div>
                </div>
              )}

              {demoStep === 3 && (
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-purple-400 uppercase tracking-widest block">Step 03 / Sub-Second Execution</span>
                  <h4 className="text-sm font-bold text-white">3. Direct Zerodha API Market Order</h4>
                  <p className="text-slate-400 text-xs font-sans leading-relaxed">
                    Within 42 milliseconds, DestinyAI selects <strong>ATM 24,100 CE</strong> option contract and fires sub-second MARKET order for 1 Lot (65 shares) @ ₹120.00 fill price.
                  </p>
                  <div className="bg-slate-900 p-3 rounded-xl border border-purple-500/30 flex justify-between items-center text-indigo-400 font-bold">
                    <span>BUY 1 Lot NIFTY 24,100 CE @ ₹120.00</span>
                    <span className="text-emerald-400 text-[10px]">FILLED IN 42ms</span>
                  </div>
                </div>
              )}

              {demoStep === 4 && (
                <div className="space-y-3">
                  <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest block">Step 04 / Automated Exit & Alert</span>
                  <h4 className="text-sm font-bold text-white">4. Target Exit (+30 Pts) & Telegram Push</h4>
                  <p className="text-slate-400 text-xs font-sans leading-relaxed">
                    Option price reaches <strong>₹150.00 (+30 pts target)</strong>. DestinyAI exits position automatically, books <strong>+₹1,950 profit</strong>, and sends Telegram alert!
                  </p>
                  <div className="bg-slate-900 p-3 rounded-xl border border-emerald-500/40 text-emerald-400 font-bold flex justify-between items-center">
                    <span>SELL 1 Lot NIFTY 24,100 CE @ ₹150.00</span>
                    <span className="text-white bg-emerald-600 px-2 py-0.5 rounded text-[10px]">+₹1,950 PROFIT</span>
                  </div>
                </div>
              )}

              {/* Modal Footer Controls */}
              <div className="pt-4 border-t border-slate-800 flex justify-between items-center font-sans">
                <button
                  onClick={() => setDemoStep(prev => (prev === 4 ? 1 : prev + 1))}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-2 rounded-xl transition-all shadow"
                >
                  {demoStep === 4 ? '🔄 Restart Demo' : 'Next Step →'}
                </button>
                <button
                  onClick={() => {
                    setShowDemoModal(false)
                    onRegisterClick()
                  }}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-4 py-2 rounded-xl transition-all shadow"
                >
                  Start Free Paper Trading Now
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
