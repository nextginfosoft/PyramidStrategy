import { useState } from 'react'
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

  const [levels, setLevels] = useState({
    r1: cfg?.r1 ?? 23170, r2: cfg?.r2 ?? 23220, r3: cfg?.r3 ?? 23250,
    s1: cfg?.s1 ?? 23070, s2: cfg?.s2 ?? 23025, s3: cfg?.s3 ?? 22950,
    lot_size: cfg?.lot_size ?? 75,
    target_points: cfg?.target_points ?? 20,
    sl_points: cfg?.sl_points ?? 10,
  })

  const [zerodha, setZerodha] = useState({ api_key: '', api_secret: '' })
  const [ai, setAi] = useState({ provider: 'openai', api_key: '' })
  const [telegram, setTelegram] = useState({ bot_token: '', chat_id: '' })
  const [paperTrade, setPaperTrade] = useState<boolean | null>(null)

  const [status, setStatus] = useState<StatusMsg | null>(null)

  const showStatus = (text: string, ok: boolean) => {
    setStatus({ text, ok })
    setTimeout(() => setStatus(null), 3000)
  }

  const saveLevels = useMutation({
    mutationFn: configApi.saveStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-config'] })
      showStatus('✓ Strategy levels saved', true)
    },
    onError: () => showStatus('✗ Failed to save levels', false),
  })

  const saveKey = useMutation({
    mutationFn: configApi.saveApiKey,
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      showStatus(`✓ ${vars.provider} key saved`, true)
    },
    onError: (_, vars) => showStatus(`✗ Failed to save ${vars.provider} key`, false),
  })

  const handleSaveLevels = (e: React.FormEvent) => {
    e.preventDefault()
    saveLevels.mutate(levels)
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
    try {
      const res = await aiApi.testConnection()
      showStatus(res.success ? `✓ AI connected (${res.provider})` : `✗ ${res.message}`, res.success)
    } catch {
      showStatus('✗ AI test failed', false)
    }
  }

  const handleTestTelegram = async () => {
    try {
      const res = await notificationApi.test()
      showStatus(res.success ? '✓ Test message sent to Telegram' : `✗ ${res.message}`, res.success)
    } catch {
      showStatus('✗ Telegram test failed', false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white">⚙ Settings</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        {/* Status bar */}
        {status && (
          <div className={`mx-4 mt-4 px-3 py-2 rounded text-sm font-medium ${status.ok ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {status.text}
          </div>
        )}

        <div className="p-4 space-y-6">
          {/* ── Paper/Live Mode ─────────────────────────────────────── */}
          <div>
            <h3 className="text-sm font-bold text-yellow-400 mb-3">⚡ Execution Mode</h3>
            <div className="flex items-center gap-4 bg-gray-800 border border-gray-700 rounded p-3">
              <button
                onClick={() => setPaperTrade(true)}
                className={`flex-1 py-2 rounded text-sm font-bold transition-colors ${
                  paperTrade === true || paperTrade === null
                    ? 'bg-yellow-700 text-yellow-100'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                📝 Paper Trade
              </button>
              <button
                onClick={() => {
                  if (window.confirm('⚠️ Switch to LIVE mode? Real orders will be placed!')) {
                    setPaperTrade(false)
                  }
                }}
                className={`flex-1 py-2 rounded text-sm font-bold transition-colors ${
                  paperTrade === false
                    ? 'bg-red-700 text-red-100'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                ⚡ Live Trade
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {paperTrade === false
                ? '⚠️ LIVE mode — real orders will be placed via Kite Connect'
                : 'Paper mode — simulated orders, no real execution'}
            </p>
          </div>

          {/* ── Strategy Levels ──────────────────────────────────────── */}
          <form onSubmit={handleSaveLevels}>
            <h3 className="text-sm font-bold text-orange-400 mb-3">📊 Strategy Levels</h3>
            <div className="grid grid-cols-3 gap-3">
              {(['r1','r2','r3'] as const).map(k => (
                <label key={k} className="block">
                  <span className="text-xs text-red-400 uppercase">{k} (PE trigger)</span>
                  <input
                    type="number"
                    className="w-full mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500"
                    value={levels[k]}
                    onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                  />
                </label>
              ))}
              {(['s1','s2','s3'] as const).map(k => (
                <label key={k} className="block">
                  <span className="text-xs text-green-400 uppercase">{k} (CE trigger)</span>
                  <input
                    type="number"
                    className="w-full mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500"
                    value={levels[k]}
                    onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                  />
                </label>
              ))}
            </div>
            <div className="mt-3 flex gap-3 items-end">
              <label className="block">
                <span className="text-xs text-gray-400">Lot Size</span>
                <input type="number" className="w-24 mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                  value={levels.lot_size} onChange={e => setLevels(p => ({...p, lot_size: +e.target.value}))} />
              </label>
              <label className="block">
                <span className="text-xs text-gray-400">Target Pts</span>
                <input type="number" className="w-20 mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                  value={levels.target_points} onChange={e => setLevels(p => ({...p, target_points: +e.target.value}))} />
              </label>
              <label className="block">
                <span className="text-xs text-gray-400">SL Pts (L3)</span>
                <input type="number" className="w-20 mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                  value={levels.sl_points} onChange={e => setLevels(p => ({...p, sl_points: +e.target.value}))} />
              </label>
            </div>
            <button type="submit"
              className="mt-3 px-4 py-2 bg-orange-600 hover:bg-orange-500 rounded text-sm font-bold text-white">
              Save Levels
            </button>
          </form>

          {/* ── Zerodha ──────────────────────────────────────────────── */}
          <div>
            <h3 className="text-sm font-bold text-blue-400 mb-3">🔗 Zerodha Kite Connect</h3>
            <div className="space-y-2">
              <input type="password" placeholder="API Key"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={zerodha.api_key} onChange={e => setZerodha(p => ({...p, api_key: e.target.value}))} />
              <input type="password" placeholder="API Secret"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={zerodha.api_secret} onChange={e => setZerodha(p => ({...p, api_secret: e.target.value}))} />
              <button onClick={handleSaveZerodha}
                className="px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded text-sm font-bold text-white">
                Save Zerodha Keys
              </button>
              {getMaskedKey('zerodha') && (
                <div className="text-xs text-gray-400 font-mono mt-1">
                  Currently configured key: <span className="text-blue-300">{getMaskedKey('zerodha')}</span>
                </div>
              )}
            </div>
          </div>

          {/* ── AI Observer ──────────────────────────────────────────── */}
          <div>
            <h3 className="text-sm font-bold text-purple-400 mb-3">🤖 AI Observer</h3>
            <div className="space-y-2">
              <select className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={ai.provider} onChange={e => setAi(p => ({...p, provider: e.target.value}))}>
                <option value="openai">OpenAI (GPT-4o)</option>
                <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                <option value="gemini">Google (Gemini 1.5 Pro)</option>
              </select>
              <input type="password" placeholder="AI API Key"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={ai.api_key} onChange={e => setAi(p => ({...p, api_key: e.target.value}))} />
              <div className="flex gap-2">
                <button onClick={handleSaveAi}
                  className="px-4 py-2 bg-purple-700 hover:bg-purple-600 rounded text-sm font-bold text-white">
                  Save AI Key
                </button>
                <button onClick={handleTestAi}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-bold text-white">
                  Test Connection
                </button>
              </div>
              {getMaskedKey(ai.provider) && (
                <div className="text-xs text-gray-400 font-mono mt-1">
                  Currently configured key: <span className="text-purple-300">{getMaskedKey(ai.provider)}</span>
                </div>
              )}
            </div>
          </div>

          {/* ── Telegram ─────────────────────────────────────────────── */}
          <div>
            <h3 className="text-sm font-bold text-sky-400 mb-3">📱 Telegram Notifications</h3>
            <p className="text-xs text-gray-500 mb-2">
              Get instant alerts for entries, targets, SL hits and squareoffs.
              Create a bot via @BotFather and get your Chat ID via @userinfobot.
            </p>
            <div className="space-y-2">
              <input type="password" placeholder="Bot Token (from @BotFather)"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={telegram.bot_token} onChange={e => setTelegram(p => ({...p, bot_token: e.target.value}))} />
              <input type="text" placeholder="Chat ID (from @userinfobot)"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={telegram.chat_id} onChange={e => setTelegram(p => ({...p, chat_id: e.target.value}))} />
              <div className="flex gap-2">
                <button onClick={handleSaveTelegram}
                  className="px-4 py-2 bg-sky-700 hover:bg-sky-600 rounded text-sm font-bold text-white">
                  Save Telegram
                </button>
                <button onClick={handleTestTelegram}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-bold text-white">
                  Send Test Message
                </button>
              </div>
              {getMaskedKey('telegram') && (
                <div className="text-xs text-gray-400 font-mono mt-1">
                  Currently configured token: <span className="text-sky-300">{getMaskedKey('telegram')}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
          All API keys are AES-256 encrypted before storage.
        </div>
      </div>
    </div>
  )
}
