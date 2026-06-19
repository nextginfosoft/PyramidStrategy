import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, aiApi, notificationApi } from '../../services/api'

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

  const [activeTab, setActiveTab] = useState<'strategy' | 'zerodha' | 'ai' | 'telegram'>('strategy')

  const [levels, setLevels] = useState({
    r1: cfg?.r1 ?? 23170, r2: cfg?.r2 ?? 23220, r3: cfg?.r3 ?? 23250,
    s1: cfg?.s1 ?? 23070, s2: cfg?.s2 ?? 23025, s3: cfg?.s3 ?? 22950,
    lot_size: cfg?.lot_size ?? 65,
    target_points: cfg?.target_points ?? 20,
    sl_points: cfg?.sl_points ?? 10,
  })

  const [zerodha, setZerodha] = useState({ api_key: '', api_secret: '' })
  const [ai, setAi] = useState({ provider: 'openai', api_key: '' })
  const [telegram, setTelegram] = useState({ bot_token: '', chat_id: '' })
  const [paperTrade, setPaperTrade] = useState<boolean | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  const [status, setStatus] = useState<StatusMsg | null>(null)
  const [testingAi, setTestingAi] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)

  useEffect(() => {
    if (cfg && !isInitialized) {
      setLevels({
        r1: cfg.r1, r2: cfg.r2, r3: cfg.r3,
        s1: cfg.s1, s2: cfg.s2, s3: cfg.s3,
        lot_size: cfg.lot_size,
        target_points: cfg.target_points,
        sl_points: cfg.sl_points,
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
    if (!ai.api_key) return
    saveKey.mutate({ provider: ai.provider, api_key: ai.api_key })
  }

  const handleSaveTelegram = () => {
    if (!telegram.bot_token || !telegram.chat_id) return
    saveKey.mutate({
      provider: 'telegram',
      api_key: telegram.bot_token,
      extra_config: { chat_id: telegram.chat_id },
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

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/50">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">⚙</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">System Settings</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-white transition-colors p-1.5 hover:bg-gray-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Custom Premium Tabs */}
        <div className="flex border-b border-gray-800 bg-gray-900/20 overflow-x-auto scrollbar-none">
          <button
            onClick={() => setActiveTab('strategy')}
            className={`flex-1 min-w-[120px] py-3 text-[11px] font-bold uppercase tracking-wider transition-all border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'strategy'
                ? 'border-orange-500 text-orange-400 bg-orange-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40'
            }`}
          >
            📊 Strategy Rules
          </button>
          <button
            onClick={() => setActiveTab('zerodha')}
            className={`flex-1 min-w-[120px] py-3 text-[11px] font-bold uppercase tracking-wider transition-all border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'zerodha'
                ? 'border-blue-500 text-blue-400 bg-blue-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40'
            }`}
          >
            🔑 Kite Connect
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('zerodha') ? 'bg-green-400 shadow-sm' : 'bg-gray-600'}`} />
          </button>
          <button
            onClick={() => setActiveTab('ai')}
            className={`flex-1 min-w-[120px] py-3 text-[11px] font-bold uppercase tracking-wider transition-all border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'ai'
                ? 'border-purple-500 text-purple-400 bg-purple-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40'
            }`}
          >
            🤖 AI Observer
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('openai') || isConfigured('anthropic') || isConfigured('gemini') ? 'bg-green-400 shadow-sm' : 'bg-gray-600'}`} />
          </button>
          <button
            onClick={() => setActiveTab('telegram')}
            className={`flex-1 min-w-[120px] py-3 text-[11px] font-bold uppercase tracking-wider transition-all border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'telegram'
                ? 'border-sky-500 text-sky-400 bg-sky-500/5'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40'
            }`}
          >
            🔔 Notifications
            <span className={`w-1.5 h-1.5 rounded-full ${isConfigured('telegram') ? 'bg-green-400 shadow-sm' : 'bg-gray-600'}`} />
          </button>
        </div>

        {/* Status Alert Notification Bar */}
        {status && (
          <div className="px-4 pt-4">
            <div className={`px-4 py-2.5 rounded-lg text-xs font-semibold flex items-center gap-2 border transition-all ${
              status.ok 
                ? 'bg-green-950/40 border-green-800 text-green-300' 
                : 'bg-red-950/40 border-red-800 text-red-300'
            }`}>
              <span>{status.ok ? '✓' : '⚠️'}</span>
              <span>{status.text}</span>
            </div>
          </div>
        )}

        {/* Tab Contents */}
        <div className="p-5 flex-1 overflow-auto space-y-5">
          
          {/* TAB 1: STRATEGY RULES */}
          {activeTab === 'strategy' && (
            <div className="space-y-5">
              {/* Execution mode card */}
              <div className="bg-gray-900/40 border border-gray-800 rounded-lg p-3">
                <span className="text-[10px] uppercase font-extrabold tracking-wider text-gray-500 block mb-2">⚡ Execution Mode</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleTogglePaperTrade(true)}
                    className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all border flex flex-col items-center justify-center ${
                      paperTrade === true || paperTrade === null
                        ? 'bg-yellow-950/40 border-yellow-700 text-yellow-400 shadow-lg shadow-yellow-950/20'
                        : 'bg-gray-900/50 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                    }`}
                  >
                    <span className="text-sm mb-0.5">📝</span>
                    <span>Paper Trading</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm('⚠️ Switch to LIVE mode? Real orders will be placed!')) {
                        handleTogglePaperTrade(false)
                      }
                    }}
                    className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all border flex flex-col items-center justify-center ${
                      paperTrade === false
                        ? 'bg-red-950/40 border-red-700 text-red-400 shadow-lg shadow-red-950/20'
                        : 'bg-gray-900/50 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                    }`}
                  >
                    <span className="text-sm mb-0.5">⚡</span>
                    <span>Live Auto Trading</span>
                  </button>
                </div>
                <p className="text-[10px] text-gray-500 mt-2 text-center">
                  {paperTrade === false
                    ? '⚠️ Warning: Orders are executed live on Zerodha Kite exchange!'
                    : 'System simulates all order executions locally based on market LTP.'}
                </p>
              </div>

              {/* Levels configurations */}
              <form onSubmit={handleSaveLevels} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  
                  {/* Bearish Levels card */}
                  <div className="bg-red-950/10 border border-red-900/20 rounded-lg p-3 space-y-3">
                    <span className="text-xs font-bold text-red-400 flex items-center gap-1.5 border-b border-red-900/20 pb-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                      Bearish Levels (Resistance / PE)
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {(['r1', 'r2', 'r3'] as const).map(k => (
                        <label key={k} className="block space-y-1">
                          <span className="text-[10px] text-gray-500 font-bold uppercase">{k} Trigger</span>
                          <input
                            type="number"
                            required
                            step="any"
                            className="w-full bg-gray-900 border border-gray-800 focus:border-red-500 focus:ring-1 focus:ring-red-500 rounded px-2.5 py-1.5 text-xs text-white font-mono transition-all"
                            value={levels[k]}
                            onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Bullish Levels card */}
                  <div className="bg-green-950/10 border border-green-900/20 rounded-lg p-3 space-y-3">
                    <span className="text-xs font-bold text-green-400 flex items-center gap-1.5 border-b border-green-900/20 pb-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                      Bullish Levels (Support / CE)
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {(['s1', 's2', 's3'] as const).map(k => (
                        <label key={k} className="block space-y-1">
                          <span className="text-[10px] text-gray-500 font-bold uppercase">{k} Trigger</span>
                          <input
                            type="number"
                            required
                            step="any"
                            className="w-full bg-gray-900 border border-gray-800 focus:border-green-500 focus:ring-1 focus:ring-green-500 rounded px-2.5 py-1.5 text-xs text-white font-mono transition-all"
                            value={levels[k]}
                            onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                </div>

                {/* Lot Size, Target, SL Parameters */}
                <div className="bg-gray-900/30 border border-gray-850 rounded-lg p-3">
                  <span className="text-[10px] uppercase font-extrabold tracking-wider text-gray-500 block mb-3">⚙ Core Parameters</span>
                  <div className="grid grid-cols-3 gap-3">
                    <label className="block space-y-1">
                      <span className="text-[10px] text-gray-400 font-medium">Lot Size (Lots)</span>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        required
                        className="w-full bg-gray-900 border border-gray-800 focus:border-orange-500 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                        value={Math.round(levels.lot_size / 65)}
                        onChange={e => {
                          const lots = +e.target.value;
                          setLevels(p => ({ ...p, lot_size: lots * 65 }));
                        }}
                      />
                      <span className="text-[9px] text-gray-600 block">1 Lot = 65 shares</span>
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[10px] text-gray-400 font-medium">Target Points</span>
                      <input
                        type="number"
                        min="1"
                        required
                        className="w-full bg-gray-900 border border-gray-800 focus:border-orange-500 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                        value={levels.target_points}
                        onChange={e => setLevels(p => ({ ...p, target_points: +e.target.value }))}
                      />
                      <span className="text-[9px] text-gray-600 block">Per position exit</span>
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[10px] text-gray-400 font-medium">SL Points (L3 Only)</span>
                      <input
                        type="number"
                        min="1"
                        required
                        className="w-full bg-gray-900 border border-gray-800 focus:border-orange-500 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                        value={levels.sl_points}
                        onChange={e => setLevels(p => ({ ...p, sl_points: +e.target.value }))}
                      />
                      <span className="text-[9px] text-gray-600 block">Active at Level 3</span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button 
                    type="submit"
                    className="px-5 py-2 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 transition-all shadow-md font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                  >
                    Save Strategy Parameters
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* TAB 2: ZERODHA KITE */}
          {activeTab === 'zerodha' && (
            <div className="space-y-4">
              <div className="bg-gray-900/40 border border-gray-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-gray-850 pb-2">
                  <span className="text-lg">🔗</span>
                  <span className="text-xs font-bold text-blue-400 uppercase tracking-wide">Zerodha Kite API Settings</span>
                </div>
                <p className="text-xs text-gray-400">
                  Connect your Zerodha Developer account. Ensure the Redirect URL matches your local instance callback address.
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">API Key</span>
                    <input 
                      type="password" 
                      placeholder="Enter API Key"
                      className="w-full bg-gray-900 border border-gray-800 focus:border-blue-500 rounded px-3 py-2 text-xs text-white font-mono transition-all"
                      value={zerodha.api_key} 
                      onChange={e => setZerodha(p => ({ ...p, api_key: e.target.value }))} 
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">API Secret</span>
                    <input 
                      type="password" 
                      placeholder="Enter API Secret"
                      className="w-full bg-gray-900 border border-gray-800 focus:border-blue-500 rounded px-3 py-2 text-xs text-white font-mono transition-all"
                      value={zerodha.api_secret} 
                      onChange={e => setZerodha(p => ({ ...p, api_secret: e.target.value }))} 
                    />
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-gray-500">
                    {getMaskedKey('zerodha') ? (
                      <span>Active Key: <code className="text-blue-400 font-mono">{getMaskedKey('zerodha')}</code></span>
                    ) : (
                      <span className="text-red-400 font-semibold">⚠️ No API Key Configured</span>
                    )}
                  </div>
                  <button 
                    onClick={handleSaveZerodha}
                    disabled={!zerodha.api_key && !zerodha.api_secret}
                    className="px-5 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
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
              <div className="bg-gray-900/40 border border-gray-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-gray-850 pb-2">
                  <span className="text-lg">🤖</span>
                  <span className="text-xs font-bold text-purple-400 uppercase tracking-wide">AI Advisory Observer</span>
                </div>
                <p className="text-xs text-gray-400">
                  Enable dynamic market observations and advisory insights. AI suggests risk levels but does NOT automate ordering.
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">Provider</span>
                    <select 
                      className="w-full bg-gray-900 border border-gray-800 focus:border-purple-500 rounded px-3 py-2 text-xs text-white transition-all cursor-pointer"
                      value={ai.provider} 
                      onChange={e => setAi(p => ({ ...p, provider: e.target.value }))}
                    >
                      <option value="openai">OpenAI (GPT-4o)</option>
                      <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                      <option value="gemini">Google (Gemini 2.5 Flash)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">API Key</span>
                    <input 
                      type="password" 
                      placeholder={`Enter API Key for ${ai.provider === 'openai' ? 'OpenAI' : ai.provider === 'anthropic' ? 'Anthropic' : 'Google Gemini'}`}
                      className="w-full bg-gray-900 border border-gray-800 focus:border-purple-500 rounded px-3 py-2 text-xs text-white font-mono transition-all"
                      value={ai.api_key} 
                      onChange={e => setAi(p => ({ ...p, api_key: e.target.value }))} 
                    />
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-gray-500">
                    {getMaskedKey(ai.provider) ? (
                      <span>Active Key: <code className="text-purple-400 font-mono">{getMaskedKey(ai.provider)}</code></span>
                    ) : (
                      <span className="text-gray-500">No key active for {ai.provider}</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={handleTestAi}
                      disabled={testingAi}
                      className="px-4 py-2 bg-gray-800 hover:bg-gray-750 disabled:opacity-40 text-xs font-semibold text-gray-300 rounded-lg flex items-center gap-1 border border-gray-700 transition"
                    >
                      {testingAi && <span className="w-2.5 h-2.5 border border-gray-300 border-t-transparent rounded-full animate-spin" />}
                      Test Link
                    </button>
                    <button 
                      onClick={handleSaveAi}
                      disabled={!ai.api_key}
                      className="px-5 py-2 bg-gradient-to-r from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
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
              <div className="bg-gray-900/40 border border-gray-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-gray-850 pb-2">
                  <span className="text-lg">📱</span>
                  <span className="text-xs font-bold text-sky-400 uppercase tracking-wide">Telegram Alerts</span>
                </div>
                <p className="text-xs text-gray-400">
                  Configure alerts for strategy execution (entries, target exits, stop loss hits, and scheduled squareoffs).
                </p>

                <div className="space-y-3 pt-1">
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">Bot Token</span>
                    <input 
                      type="password" 
                      placeholder="Enter Bot Token (e.g. 123456:ABC-DEF)"
                      className="w-full bg-gray-900 border border-gray-800 focus:border-sky-500 rounded px-3 py-2 text-xs text-white font-mono transition-all"
                      value={telegram.bot_token} 
                      onChange={e => setTelegram(p => ({ ...p, bot_token: e.target.value }))} 
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-gray-500 font-bold uppercase">Chat ID</span>
                    <input 
                      type="text" 
                      placeholder="Enter Chat ID (e.g. 987654321)"
                      className="w-full bg-gray-900 border border-gray-800 focus:border-sky-500 rounded px-3 py-2 text-xs text-white font-mono transition-all"
                      value={telegram.chat_id} 
                      onChange={e => setTelegram(p => ({ ...p, chat_id: e.target.value }))} 
                    />
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <div className="text-[10px] text-gray-500">
                    {getMaskedKey('telegram') ? (
                      <span>Active Token: <code className="text-sky-400 font-mono">{getMaskedKey('telegram')}</code></span>
                    ) : (
                      <span className="text-gray-500">No active notification channel</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={handleTestTelegram}
                      disabled={testingTelegram}
                      className="px-4 py-2 bg-gray-800 hover:bg-gray-750 disabled:opacity-40 text-xs font-semibold text-gray-300 rounded-lg flex items-center gap-1 border border-gray-700 transition"
                    >
                      {testingTelegram && <span className="w-2.5 h-2.5 border border-gray-300 border-t-transparent rounded-full animate-spin" />}
                      Test Alert
                    </button>
                    <button 
                      onClick={handleSaveTelegram}
                      disabled={!telegram.bot_token || !telegram.chat_id}
                      className="px-5 py-2 bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 disabled:opacity-40 transition-all font-bold text-xs uppercase tracking-wider text-white rounded-lg"
                    >
                      Save Configuration
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800 bg-gray-900/50 flex items-center justify-between text-[10px] text-gray-500">
          <span>🛡 API keys are securely stored with AES-256 encryption.</span>
          <span>v1.0.0</span>
        </div>
      </div>
    </div>
  )
}
