import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, aiApi, notificationApi } from '../../services/api'
import { Notification } from '../Notification/Notification'

type StatusMsg = { text: string; ok: boolean }

export function Settings({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: cfg } = useQuery({ queryKey: ['strategy-config'], queryFn: configApi.getStrategy })
  const { data: apiKeys } = useQuery({ queryKey: ['api-keys'], queryFn: configApi.getApiKeys })

  const getMaskedKey = (provider: string) => {
    return apiKeys?.find((k: any) => k.provider === provider)?.api_key_masked
  }

  const isConfigured = (provider: string) => {
    return !!apiKeys?.find((k: any) => k.provider === provider)?.api_key_masked
  }

  const [activeTab, setActiveTab] = useState<'strategy' | 'zerodha' | 'ai' | 'telegram' | 'whatsapp' | 'reporting'>('strategy')

  const [levels, setLevels] = useState({
    r1: cfg?.r1 ?? 23170, r2: cfg?.r2 ?? 23220, r3: cfg?.r3 ?? 23250,
    s1: cfg?.s1 ?? 23070, s2: cfg?.s2 ?? 23025, s3: cfg?.s3 ?? 22950,
    lot_size: cfg?.lot_size ?? 65,
    target_points: cfg?.target_points ?? 20,
    sl_points: cfg?.sl_points ?? 10,
    squareoff_time: cfg?.squareoff_time ?? '11:30',
  })

  const [zerodha, setZerodha] = useState({ api_key: '', api_secret: '' })
  const [ai, setAi] = useState({ provider: 'openai', api_key: '' })
  const [telegram, setTelegram] = useState({ bot_token: '', chat_id: '' })
  const [whatsapp, setWhatsapp] = useState({
    provider_type: 'meta',
    access_token: '',
    phone_number_id: '',
    recipient_phone: '',
    twilio_sid: '',
    twilio_auth_token: '',
    twilio_from: '',
    twilio_to: ''
  })
  const [reportingFormat, setReportingFormat] = useState('telegram')
  const [paperTrade, setPaperTrade] = useState<boolean | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  const [status, setStatus] = useState<StatusMsg | null>(null)
  const [testingAi, setTestingAi] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [testingWhatsapp, setTestingWhatsapp] = useState(false)

  // Password visibility states
  const [showZerodhaKey, setShowZerodhaKey] = useState(false)
  const [showZerodhaSecret, setShowZerodhaSecret] = useState(false)
  const [showAiKey, setShowAiKey] = useState(false)
  const [showTelegramToken, setShowTelegramToken] = useState(false)
  const [showWhatsappToken, setShowWhatsappToken] = useState(false)
  const [showTwilioAuth, setShowTwilioAuth] = useState(false)

  useEffect(() => {
    if (apiKeys) {
      const telegramKey = apiKeys.find((k: any) => k.provider === 'telegram');
      if (telegramKey && telegramKey.extra_config) {
        setTelegram(p => ({
          ...p,
          chat_id: telegramKey.extra_config.chat_id || ''
        }));
      }

      const whatsappKey = apiKeys.find((k: any) => k.provider === 'whatsapp');
      if (whatsappKey && whatsappKey.extra_config) {
        const extra = whatsappKey.extra_config;
        setWhatsapp(p => ({
          ...p,
          provider_type: extra.provider_type || 'meta',
          phone_number_id: extra.phone_number_id || '',
          recipient_phone: extra.recipient_phone || '',
          twilio_from: extra.from_phone || '',
          twilio_to: extra.to_phone || ''
        }));
      }

      const reportingKey = apiKeys.find((k: any) => k.provider === 'reporting');
      if (reportingKey && reportingKey.extra_config) {
        setReportingFormat(reportingKey.extra_config.format || 'telegram');
      }

      const activeAiKey = apiKeys.find((k: any) => ['openai', 'anthropic', 'gemini'].includes(k.provider) && k.is_active);
      if (activeAiKey) {
        setAi(p => ({
          ...p,
          provider: activeAiKey.provider
        }));
      }
    }
  }, [apiKeys]);

  useEffect(() => {
    if (cfg && !isInitialized) {
      setLevels({
        r1: cfg.r1, r2: cfg.r2, r3: cfg.r3,
        s1: cfg.s1, s2: cfg.s2, s3: cfg.s3,
        lot_size: cfg.lot_size,
        target_points: cfg.target_points,
        sl_points: cfg.sl_points,
        squareoff_time: cfg.squareoff_time ?? '11:30',
      })
      if (cfg.paper_trade !== undefined) {
        setPaperTrade(cfg.paper_trade)
      }
      setIsInitialized(true)
    }
  }, [cfg, isInitialized])

  const handleTogglePaperTrade = (value: boolean) => {
    setPaperTrade(value)
    saveLevels.mutate({
      ...levels,
      paper_trade: value,
    })
  }

  const showStatus = (text: string, ok: boolean) => {
    setStatus({ text, ok })
    setTimeout(() => setStatus(null), 4000)
  }

  const saveLevels = useMutation({
    mutationFn: configApi.saveStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-config'] })
      showStatus('✓ Strategy configurations saved successfully', true)
    },
    onError: (err: any) => {
      let errMsg = 'Failed to save strategy configuration';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail) && detail.length > 0) {
          const firstErr = detail[0];
          errMsg = firstErr.msg || errMsg;
          if (errMsg.startsWith('Value error, ')) {
            errMsg = errMsg.substring('Value error, '.length);
          }
        } else if (typeof detail === 'string') {
          errMsg = detail;
        }
      }
      showStatus(`✗ ${errMsg}`, false);
    },
  })

  const saveKey = useMutation({
    mutationFn: configApi.saveApiKey,
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      showStatus(`✓ ${vars.provider.toUpperCase()} credentials saved successfully`, true)
      if (vars.provider === 'zerodha') setZerodha({ api_key: '', api_secret: '' })
      if (vars.provider === ai.provider) setAi(p => ({ ...p, api_key: '' }))
      if (vars.provider === 'telegram') setTelegram(p => ({ ...p, bot_token: '' }))
      if (vars.provider === 'whatsapp') setWhatsapp(p => ({ ...p, access_token: '', twilio_auth_token: '' }))
    },
    onError: (_, vars) => showStatus(`✗ Failed to save ${vars.provider.toUpperCase()} credentials`, false),
  })

  const handleSaveLevels = (e: React.FormEvent) => {
    e.preventDefault()

    const { r1, r2, r3, s1, s2, s3 } = levels;

    if (s1 <= s2 || s2 <= s3) {
      showStatus('✗ Support levels must be descending (S1 > S2 > S3)', false)
      return
    }

    if (r1 >= r2 || r2 >= r3) {
      showStatus('✗ Resistance levels must be ascending (R1 < R2 < R3)', false)
      return
    }

    saveLevels.mutate({
      ...levels,
      paper_trade: paperTrade ?? true,
    })
  }

  const handleSaveZerodha = () => {
    if (!zerodha.api_key && !zerodha.api_secret) return
    saveKey.mutate({ provider: 'zerodha', api_key: zerodha.api_key, api_secret: zerodha.api_secret })
  }

  const handleSaveAi = () => {
    saveKey.mutate({ provider: ai.provider, api_key: ai.api_key || undefined })
  }

  const handleSaveTelegram = () => {
    if (!telegram.chat_id) return
    saveKey.mutate({
      provider: 'telegram',
      api_key: telegram.bot_token || undefined,
      extra_config: { chat_id: telegram.chat_id },
    })
  }

  const handleSaveWhatsapp = () => {
    if (whatsapp.provider_type === 'meta') {
      if (!whatsapp.phone_number_id || !whatsapp.recipient_phone) return
      saveKey.mutate({
        provider: 'whatsapp',
        api_key: whatsapp.access_token || undefined,
        extra_config: {
          provider_type: 'meta',
          phone_number_id: whatsapp.phone_number_id,
          recipient_phone: whatsapp.recipient_phone
        }
      })
    } else {
      if (!whatsapp.twilio_from || !whatsapp.twilio_to) return
      saveKey.mutate({
        provider: 'whatsapp',
        api_key: whatsapp.twilio_sid || undefined,
        api_secret: whatsapp.twilio_auth_token || undefined,
        extra_config: {
          provider_type: 'twilio',
          from_phone: whatsapp.twilio_from,
          to_phone: whatsapp.twilio_to
        }
      })
    }
  }

  const handleSaveReporting = () => {
    saveKey.mutate({
      provider: 'reporting',
      extra_config: { format: reportingFormat }
    })
  }

  const handleTestAi = async () => {
    setTestingAi(true)
    try {
      const res = await aiApi.testConnection()
      showStatus(res.success ? `✓ AI connection test passed (${res.provider})` : `✗ Connection failed: ${res.message}`, res.success)
    } catch {
      showStatus('✗ AI test request failed', false)
    } finally {
      setTestingAi(false)
    }
  }

  const handleTestTelegram = async () => {
    setTestingTelegram(true)
    try {
      const res = await notificationApi.test()
      showStatus(res.success ? '✓ Test message dispatched to Telegram' : `✗ Telegram failed: ${res.message}`, res.success)
    } catch {
      showStatus('✗ Telegram test request failed', false)
    } finally {
      setTestingTelegram(false)
    }
  }

  const handleTestWhatsapp = async () => {
    setTestingWhatsapp(true)
    try {
      const res = await notificationApi.testWhatsapp()
      showStatus(res.success ? '✓ Test message dispatched to WhatsApp' : `✗ WhatsApp failed: ${res.message}`, res.success)
    } catch {
      showStatus('✗ WhatsApp test request failed', false)
    } finally {
      setTestingWhatsapp(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
      <div className="bg-navy-950/90 border border-navy-700/80 rounded-2xl w-full max-w-2xl shadow-2xl shadow-blue-500/5 overflow-hidden flex flex-col max-h-[90vh] backdrop-blur-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/40">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">⚙</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">System Configuration</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-navy-300 hover:text-white transition-colors p-1.5 hover:bg-navy-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Custom Premium Tabs with color coordination */}
        <div className="flex border-b border-navy-700/80 bg-navy-900/20 overflow-x-auto scrollbar-none p-1 gap-1">
          <button
            onClick={() => setActiveTab('strategy')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'strategy'
                ? 'bg-orange-500/10 text-orange-400 border border-orange-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            📊 Strategy
          </button>
          <button
            onClick={() => setActiveTab('zerodha')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'zerodha'
                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            🔑 Kite Connect
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('zerodha') ? 'bg-green-400 shadow-sm shadow-green-500/50 animate-pulse' : 'bg-navy-700'}`} />
          </button>
          <button
            onClick={() => setActiveTab('ai')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'ai'
                ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            🤖 AI Observer
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('openai') || isConfigured('anthropic') || isConfigured('gemini') ? 'bg-green-400 shadow-sm shadow-green-500/50 animate-pulse' : 'bg-navy-700'}`} />
          </button>
          <button
            onClick={() => setActiveTab('telegram')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'telegram'
                ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            🔔 Telegram
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('telegram') ? 'bg-green-400 shadow-sm shadow-green-500/50 animate-pulse' : 'bg-navy-700'}`} />
          </button>
          <button
            onClick={() => setActiveTab('whatsapp')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'whatsapp'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            💬 WhatsApp
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('whatsapp') ? 'bg-green-400 shadow-sm shadow-green-500/50 animate-pulse' : 'bg-navy-700'}`} />
          </button>
          <button
            onClick={() => setActiveTab('reporting')}
            className={`flex-1 min-w-[110px] py-2.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'reporting'
                ? 'bg-teal-500/10 text-teal-400 border border-teal-500/30'
                : 'border border-transparent text-navy-300 hover:text-navy-100 hover:bg-navy-900/40'
            }`}
          >
            📋 Reports
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('reporting') ? 'bg-green-400 shadow-sm shadow-green-500/50 animate-pulse' : 'bg-navy-700'}`} />
          </button>
        </div>


        {/* Status Alert Notification Bar */}
        {status && (
          <div className="px-5 pt-4">
            <Notification
              type={status.ok ? 'success' : 'error'}
              message={status.text}
              onClose={() => setStatus(null)}
            />
          </div>
        )}

        {/* Tab Contents */}
        <div className="p-5 flex-1 overflow-auto space-y-5">
          
          {/* TAB 1: STRATEGY RULES */}
          {activeTab === 'strategy' && (
            <div className="space-y-5">
              {/* Execution mode card */}
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4">
                <span className="text-[10px] uppercase font-bold tracking-wider text-navy-300 block mb-2.5">⚡ Execution Channel</span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => handleTogglePaperTrade(true)}
                    className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center ${
                      paperTrade === true || paperTrade === null
                        ? 'bg-amber-500/10 border-amber-500/40 text-amber-400 shadow-lg shadow-amber-950/20'
                        : 'bg-navy-900/40 border-navy-700 text-navy-300 hover:border-navy-600 hover:text-navy-100'
                    }`}
                  >
                    <span className="text-base mb-1">📝</span>
                    <span>Paper Trading</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm('⚠️ Switch to LIVE mode? Real orders will be placed!')) {
                        handleTogglePaperTrade(false)
                      }
                    }}
                    className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center ${
                      paperTrade === false
                        ? 'bg-red-500/10 border-red-500/40 text-red-400 shadow-lg shadow-red-950/20'
                        : 'bg-navy-900/40 border-navy-700 text-navy-300 hover:border-navy-600 hover:text-navy-100'
                    }`}
                  >
                    <span className="text-base mb-1">⚡</span>
                    <span>Live Auto Trading</span>
                  </button>
                </div>
                <p className="text-[10px] text-navy-300 mt-2.5 text-center">
                  {paperTrade === false
                    ? '⚠️ Warning: Orders are executed live on Zerodha Kite exchange!'
                    : 'System simulates all order executions locally based on market LTP.'}
                </p>
              </div>

              {/* Levels configurations */}
              <form onSubmit={handleSaveLevels} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  
                  {/* Bearish Levels card */}
                  <div className="bg-red-950/5 border border-red-900/20 rounded-xl p-4 space-y-3">
                    <span className="text-xs font-bold text-red-400 flex items-center gap-1.5 border-b border-red-900/20 pb-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                      Bearish Levels (Resistance / PE)
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {(['r1', 'r2', 'r3'] as const).map(k => (
                        <label key={k} className="block space-y-1">
                          <span className="text-[9px] text-navy-300 font-bold uppercase">{k} Level</span>
                          <input
                            type="number"
                            required
                            step="any"
                            className="w-full bg-navy-900 border border-navy-700 focus:border-red-500/70 focus:ring-1 focus:ring-red-500/30 rounded px-2.5 py-1.5 text-xs text-white font-mono transition-all"
                            value={levels[k]}
                            onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Bullish Levels card */}
                  <div className="bg-green-950/5 border border-green-900/20 rounded-xl p-4 space-y-3">
                    <span className="text-xs font-bold text-green-400 flex items-center gap-1.5 border-b border-green-900/20 pb-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                      Bullish Levels (Support / CE)
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {(['s1', 's2', 's3'] as const).map(k => (
                        <label key={k} className="block space-y-1">
                          <span className="text-[9px] text-navy-300 font-bold uppercase">{k} Level</span>
                          <input
                            type="number"
                            required
                            step="any"
                            className="w-full bg-navy-900 border border-navy-700 focus:border-green-500/70 focus:ring-1 focus:ring-green-500/30 rounded px-2.5 py-1.5 text-xs text-white font-mono transition-all"
                            value={levels[k]}
                            onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Core Parameters card */}
                <div className="bg-navy-900/20 border border-navy-700 rounded-xl p-4">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-navy-300 block mb-3">⚙ Core Parameters</span>
                  <div className="grid grid-cols-4 gap-3">
                    <div className="block space-y-1">
                      <span className="text-[10px] text-navy-300 font-medium">Lot Size (Lots)</span>
                      <div className="relative">
                        <input
                          type="number"
                          min="1"
                          step="1"
                          required
                          className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded pl-8 pr-3 py-1.5 text-xs text-white font-mono"
                          value={Math.round(levels.lot_size / 65)}
                          onChange={e => {
                            const lots = +e.target.value;
                            setLevels(p => ({ ...p, lot_size: lots * 65 }));
                          }}
                        />
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">📦</span>
                      </div>
                      <span className="text-[9px] text-navy-400 block">1 Lot = 65 shares</span>
                    </div>

                    <div className="block space-y-1">
                      <span className="text-[10px] text-navy-300 font-medium">Target Points</span>
                      <div className="relative">
                        <input
                          type="number"
                          min="1"
                          required
                          className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded pl-8 pr-3 py-1.5 text-xs text-white font-mono"
                          value={levels.target_points}
                          onChange={e => setLevels(p => ({ ...p, target_points: +e.target.value }))}
                        />
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🎯</span>
                      </div>
                      <span className="text-[9px] text-navy-400 block">Per position exit</span>
                    </div>

                    <div className="block space-y-1">
                      <span className="text-[10px] text-navy-300 font-medium">SL Points (L3 Only)</span>
                      <div className="relative">
                        <input
                          type="number"
                          min="1"
                          required
                          className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded pl-8 pr-3 py-1.5 text-xs text-white font-mono"
                          value={levels.sl_points}
                          onChange={e => setLevels(p => ({ ...p, sl_points: +e.target.value }))}
                        />
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🛑</span>
                      </div>
                      <span className="text-[9px] text-navy-400 block">Active at Level 3</span>
                    </div>

                    <div className="block space-y-1">
                      <span className="text-[10px] text-navy-300 font-medium">Squareoff Time</span>
                      <div className="relative">
                        <input
                          type="text"
                          pattern="^(0[9]|1[0-5]):[0-5][0-9]$"
                          placeholder="11:30"
                          required
                          className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded pl-8 pr-3 py-1.5 text-xs text-white font-mono"
                          value={levels.squareoff_time}
                          onChange={e => setLevels(p => ({ ...p, squareoff_time: e.target.value }))}
                        />
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">⏰</span>
                      </div>
                      <span className="text-[9px] text-navy-400 block">Cutoff = 15m prior</span>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button 
                    type="submit"
                    className="px-5 py-2.5 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 transition-all shadow-md font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                  >
                    Save Parameters
                  </button>
                </div>
              </form>
            </div>
          )}


          {/* TAB 2: ZERODHA KITE */}
          {activeTab === 'zerodha' && (
            <div className="space-y-4">
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-navy-700 pb-2">
                  <span className="text-lg">🔗</span>
                  <span className="text-xs font-bold text-blue-400 uppercase tracking-wide">Zerodha Kite API Settings</span>
                </div>
                <p className="text-xs text-navy-300">
                  Connect your Zerodha Developer account. Ensure the Redirect URL matches your local instance callback address.
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">API Key</span>
                    <div className="relative">
                      <input 
                        type={showZerodhaKey ? "text" : "password"} 
                        placeholder="Enter API Key"
                        className="w-full bg-navy-900 border border-navy-700 focus:border-blue-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                        value={zerodha.api_key} 
                        onChange={e => setZerodha(p => ({ ...p, api_key: e.target.value }))} 
                      />
                      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔑</span>
                      <button
                        type="button"
                        onClick={() => setShowZerodhaKey(!showZerodhaKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                      >
                        {showZerodhaKey ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">API Secret</span>
                    <div className="relative">
                      <input 
                        type={showZerodhaSecret ? "text" : "password"} 
                        placeholder="Enter API Secret"
                        className="w-full bg-navy-900 border border-navy-700 focus:border-blue-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                        value={zerodha.api_secret} 
                        onChange={e => setZerodha(p => ({ ...p, api_secret: e.target.value }))} 
                      />
                      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔒</span>
                      <button
                        type="button"
                        onClick={() => setShowZerodhaSecret(!showZerodhaSecret)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                      >
                        {showZerodhaSecret ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-navy-300">
                    {getMaskedKey('zerodha') ? (
                      <span>Active Key: <code className="text-blue-400 font-mono">{getMaskedKey('zerodha')}</code></span>
                    ) : (
                      <span className="text-red-400 font-semibold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" /> No API Key Configured
                      </span>
                    )}
                  </div>
                  <button 
                    onClick={handleSaveZerodha}
                    disabled={!zerodha.api_key && !zerodha.api_secret}
                    className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                  >
                    Save API Credentials
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: AI OBSERVER */}
          {activeTab === 'ai' && (
            <div className="space-y-4">
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-navy-700 pb-2">
                  <span className="text-lg">🤖</span>
                  <span className="text-xs font-bold text-purple-400 uppercase tracking-wide">AI Advisory Observer</span>
                </div>
                <p className="text-xs text-navy-300">
                  Enable dynamic market observations and advisory insights. AI suggests risk levels but does NOT automate ordering.
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">Provider</span>
                    <div className="flex border border-navy-700 bg-navy-950 p-0.5 rounded-lg">
                      {(['openai', 'anthropic', 'gemini'] as const).map(p => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setAi(prev => ({ ...prev, provider: p }))}
                          className={`flex-1 py-1.5 text-[10px] font-bold uppercase rounded-md transition-all ${
                            ai.provider === p
                              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                              : 'text-navy-300 hover:text-navy-100'
                          }`}
                        >
                          {p === 'openai' ? 'OpenAI' : p === 'anthropic' ? 'Anthropic' : 'Gemini'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">API Key</span>
                    <div className="relative">
                      <input 
                        type={showAiKey ? "text" : "password"} 
                        placeholder={`Enter API Key for ${ai.provider === 'openai' ? 'OpenAI' : ai.provider === 'anthropic' ? 'Anthropic' : 'Google Gemini'}`}
                        className="w-full bg-navy-900 border border-navy-700 focus:border-purple-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                        value={ai.api_key} 
                        onChange={e => setAi(p => ({ ...p, api_key: e.target.value }))} 
                      />
                      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔑</span>
                      <button
                        type="button"
                        onClick={() => setShowAiKey(!showAiKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                      >
                        {showAiKey ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-navy-300">
                    {getMaskedKey(ai.provider) ? (
                      <span>Active Key: <code className="text-purple-400 font-mono">{getMaskedKey(ai.provider)}</code></span>
                    ) : (
                      <span className="text-navy-300">No key active for {ai.provider}</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={handleTestAi}
                      disabled={testingAi}
                      className="px-4 py-2 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-xs font-semibold text-navy-200 rounded-lg flex items-center gap-1 border border-navy-700 transition"
                    >
                      {testingAi && <span className="w-2.5 h-2.5 border border-navy-300 border-t-transparent rounded-full animate-spin" />}
                      Test Link
                    </button>
                    <button 
                      onClick={handleSaveAi}
                      disabled={!isConfigured(ai.provider) && !ai.api_key}
                      className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                    >
                      Save Key
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: TELEGRAM NOTIFICATIONS */}
          {activeTab === 'telegram' && (
            <div className="space-y-4">
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-navy-700 pb-2">
                  <span className="text-lg">📱</span>
                  <span className="text-xs font-bold text-sky-400 uppercase tracking-wide">Telegram Alerts</span>
                </div>
                <p className="text-xs text-navy-300">
                  Configure alerts for strategy execution (entries, target exits, stop loss hits, and scheduled squareoffs).
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">Bot Token</span>
                    <div className="relative">
                      <input 
                        type={showTelegramToken ? "text" : "password"} 
                        placeholder="Enter Bot Token (e.g. 123456:ABC-DEF)"
                        className="w-full bg-navy-900 border border-navy-700 focus:border-sky-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                        value={telegram.bot_token} 
                        onChange={e => setTelegram(p => ({ ...p, bot_token: e.target.value }))} 
                      />
                      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔑</span>
                      <button
                        type="button"
                        onClick={() => setShowTelegramToken(!showTelegramToken)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                      >
                        {showTelegramToken ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">Chat ID</span>
                    <div className="relative">
                      <input 
                        type="text" 
                        placeholder="Enter Chat ID (e.g. 987654321)"
                        className="w-full bg-navy-900 border border-navy-700 focus:border-sky-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                        value={telegram.chat_id} 
                        onChange={e => setTelegram(p => ({ ...p, chat_id: e.target.value }))} 
                      />
                      <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">💬</span>
                    </div>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-navy-300">
                    {getMaskedKey('telegram') ? (
                      <span>Active Token: <code className="text-sky-400 font-mono">{getMaskedKey('telegram')}</code></span>
                    ) : (
                      <span className="text-navy-300 font-medium">No active notification channel</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={handleTestTelegram}
                      disabled={testingTelegram}
                      className="px-4 py-2 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-xs font-semibold text-navy-200 rounded-lg flex items-center gap-1 border border-navy-700 transition"
                    >
                      {testingTelegram && <span className="w-2.5 h-2.5 border border-navy-300 border-t-transparent rounded-full animate-spin" />}
                      Test Alert
                    </button>
                    <button 
                      onClick={handleSaveTelegram}
                      disabled={!telegram.chat_id || (!isConfigured('telegram') && !telegram.bot_token)}
                      className="px-5 py-2.5 bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                    >
                      Save Configuration
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: WHATSAPP NOTIFICATIONS */}
          {activeTab === 'whatsapp' && (
            <div className="space-y-4">
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-navy-700 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">💬</span>
                    <span className="text-xs font-bold text-emerald-400 uppercase tracking-wide">WhatsApp Alerts</span>
                  </div>
                  <div className="flex rounded-lg overflow-hidden border border-navy-700 bg-navy-950 p-0.5">
                    <button
                      onClick={() => setWhatsapp(p => ({ ...p, provider_type: 'meta' }))}
                      className={`px-3 py-1 text-[10px] font-semibold uppercase rounded transition-all ${
                        whatsapp.provider_type === 'meta'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'text-navy-300 hover:text-navy-100'
                      }`}
                    >
                      Meta Cloud
                    </button>
                    <button
                      onClick={() => setWhatsapp(p => ({ ...p, provider_type: 'twilio' }))}
                      className={`px-3 py-1 text-[10px] font-semibold uppercase rounded transition-all ${
                        whatsapp.provider_type === 'twilio'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'text-navy-300 hover:text-navy-100'
                      }`}
                    >
                      Twilio
                    </button>
                  </div>
                </div>
                <p className="text-xs text-navy-300">
                  Configure alerts for strategy execution (entries, target exits, stop loss hits, and scheduled squareoffs) to be delivered on WhatsApp.
                </p>

                <div className="space-y-3 pt-1">
                  {whatsapp.provider_type === 'meta' ? (
                    <>
                      <div className="space-y-1">
                        <span className="text-[10px] text-navy-300 font-bold uppercase">Meta Access Token</span>
                        <div className="relative">
                          <input
                            type={showWhatsappToken ? "text" : "password"}
                            placeholder={getMaskedKey('whatsapp') ? "••••••••••••••••" : "Enter Meta Graph API Access Token"}
                            className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                            value={whatsapp.access_token}
                            onChange={e => setWhatsapp(p => ({ ...p, access_token: e.target.value }))}
                          />
                          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔑</span>
                          <button
                            type="button"
                            onClick={() => setShowWhatsappToken(!showWhatsappToken)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                          >
                            {showWhatsappToken ? 'Hide' : 'Show'}
                          </button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">Phone Number ID</span>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="e.g. 1092837498"
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.phone_number_id}
                              onChange={e => setWhatsapp(p => ({ ...p, phone_number_id: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🆔</span>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">Recipient Phone</span>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="e.g. +919999999999"
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.recipient_phone}
                              onChange={e => setWhatsapp(p => ({ ...p, recipient_phone: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">📞</span>
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">Twilio Account SID</span>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder={isConfigured('whatsapp') ? "Configured (Masked)" : "ACxxxxxxxxxxxxxxxx"}
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.twilio_sid}
                              onChange={e => setWhatsapp(p => ({ ...p, twilio_sid: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🆔</span>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">Twilio Auth Token</span>
                          <div className="relative">
                            <input
                              type={showTwilioAuth ? "text" : "password"}
                              placeholder={isConfigured('whatsapp') ? "••••••••••••••••" : "Enter Auth Token"}
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-12 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.twilio_auth_token}
                              onChange={e => setWhatsapp(p => ({ ...p, twilio_auth_token: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">🔒</span>
                            <button
                              type="button"
                              onClick={() => setShowTwilioAuth(!showTwilioAuth)}
                              className="absolute right-2 top-1/2 -translate-y-1/2 text-navy-300 hover:text-white px-2 py-1 text-[10px] font-semibold"
                            >
                              {showTwilioAuth ? 'Hide' : 'Show'}
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">From Number (Sandbox)</span>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="e.g. +14155238886"
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.twilio_from}
                              onChange={e => setWhatsapp(p => ({ ...p, twilio_from: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">📞</span>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[10px] text-navy-300 font-bold uppercase">To Number</span>
                          <div className="relative">
                            <input
                              type="text"
                              placeholder="e.g. +919999999999"
                              className="w-full bg-navy-900 border border-navy-700 focus:border-green-500 rounded pl-8 pr-3 py-2 text-xs text-white font-mono transition-all"
                              value={whatsapp.twilio_to}
                              onChange={e => setWhatsapp(p => ({ ...p, twilio_to: e.target.value }))}
                            />
                            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-navy-300 text-xs">📞</span>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-navy-300 font-medium">
                    {isConfigured('whatsapp') ? (
                      <span>WhatsApp channel configured.</span>
                    ) : (
                      <span className="text-navy-300">No active notification channel</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleTestWhatsapp}
                      disabled={testingWhatsapp}
                      className="px-4 py-2 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-xs font-semibold text-navy-200 rounded-lg flex items-center gap-1 border border-navy-700 transition"
                    >
                      {testingWhatsapp && <span className="w-2.5 h-2.5 border border-navy-300 border-t-transparent rounded-full animate-spin" />}
                      Test Alert
                    </button>
                    <button
                      onClick={handleSaveWhatsapp}
                      disabled={whatsapp.provider_type === 'meta' ? (!whatsapp.phone_number_id || !whatsapp.recipient_phone) : (!whatsapp.twilio_from || !whatsapp.twilio_to)}
                      className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                    >
                      Save Configuration
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: REPORTING PREFERENCES */}
          {activeTab === 'reporting' && (
            <div className="space-y-4">
              <div className="bg-navy-900/30 border border-navy-700 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-navy-700 pb-2">
                  <span className="text-lg">📋</span>
                  <span className="text-xs font-bold text-teal-400 uppercase tracking-wide">Automated Daily Reporting</span>
                </div>
                <p className="text-xs text-navy-300">
                  Track long-term performance without manual work. Select your preferred daily and weekly summary briefing delivery format.
                </p>

                <div className="space-y-4 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-navy-300 font-bold uppercase">Delivery Format</span>
                    <select
                      value={reportingFormat}
                      onChange={e => setReportingFormat(e.target.value)}
                      className="w-full bg-navy-900 border border-navy-700 focus:border-teal-500 rounded px-3 py-2 text-xs text-white transition-all font-semibold cursor-pointer"
                    >
                      <option value="telegram">Telegram Text Message</option>
                      <option value="whatsapp">WhatsApp Text Message</option>
                      <option value="pdf">PDF Attachment (sent via Telegram/WhatsApp)</option>
                    </select>
                  </div>

                  <div className="bg-teal-950/20 border border-teal-900/40 rounded-xl p-4 text-xs text-teal-400 space-y-2.5">
                    <div className="font-bold flex items-center gap-1.5 text-white">
                      <span>⏰</span> Automated Delivery Schedule:
                    </div>
                    <ul className="list-disc pl-4 space-y-2 text-navy-200">
                      <li><strong className="text-teal-400">Daily EOD report</strong> generated at <strong className="text-teal-400">12:30 PM</strong> (Includes today's trades, gross/net P&L, strategy decisions, and AI observations).</li>
                      <li><strong className="text-teal-400">Weekly Summary report</strong> generated on <strong className="text-teal-400">Monday at 9:00 AM</strong> (Prior week stats Monday to Friday breakdown).</li>
                    </ul>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={handleSaveReporting}
                    className="px-5 py-2.5 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                  >
                    Save Preferences
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-navy-700/85 bg-navy-900/50 flex items-center justify-between text-[10px] text-navy-300 px-5">
          <span>🛡 API keys are securely stored with AES-256 encryption.</span>
          <span>v1.0.0</span>
        </div>
      </div>
    </div>
  )
}

