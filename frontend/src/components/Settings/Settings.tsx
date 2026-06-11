import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi } from '../../services/api'

export function Settings({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: cfg } = useQuery({ queryKey: ['strategy-config'], queryFn: configApi.getStrategy })

  const [levels, setLevels] = useState({
    r1: cfg?.r1 ?? 23170, r2: cfg?.r2 ?? 23220, r3: cfg?.r3 ?? 23250,
    s1: cfg?.s1 ?? 23070, s2: cfg?.s2 ?? 23025, s3: cfg?.s3 ?? 22950,
    lot_size: cfg?.lot_size ?? 75,
    target_points: cfg?.target_points ?? 20,
    sl_points: cfg?.sl_points ?? 10,
  })

  const [zerodha, setZerodha] = useState({ api_key: '', api_secret: '' })
  const [ai, setAi] = useState({ provider: 'openai', api_key: '' })
  const [saved, setSaved] = useState(false)

  const saveLevels = useMutation({
    mutationFn: configApi.saveStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategy-config'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const saveKey = useMutation({ mutationFn: configApi.saveApiKey })

  const handleSaveLevels = (e: React.FormEvent) => {
    e.preventDefault()
    saveLevels.mutate(levels)
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white">⚙ Settings</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="p-4 space-y-6">
          {/* Strategy Levels */}
          <form onSubmit={handleSaveLevels}>
            <h3 className="text-sm font-bold text-orange-400 mb-3">📊 Strategy Levels</h3>
            <div className="grid grid-cols-3 gap-3">
              {(['r1','r2','r3'] as const).map(k => (
                <label key={k} className="block">
                  <span className="text-xs text-red-400 uppercase">{k}</span>
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
                  <span className="text-xs text-green-400 uppercase">{k}</span>
                  <input
                    type="number"
                    className="w-full mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500"
                    value={levels[k]}
                    onChange={e => setLevels(p => ({ ...p, [k]: +e.target.value }))}
                  />
                </label>
              ))}
            </div>
            <div className="mt-3 flex gap-3">
              <label className="block">
                <span className="text-xs text-gray-400">Lot Size</span>
                <input type="number" className="w-24 mt-1 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                  value={levels.lot_size} onChange={e => setLevels(p => ({...p, lot_size: +e.target.value}))} />
              </label>
            </div>
            <button type="submit"
              className="mt-3 px-4 py-2 bg-orange-600 hover:bg-orange-500 rounded text-sm font-bold text-white">
              {saved ? '✓ Saved!' : 'Save Levels'}
            </button>
          </form>

          {/* Zerodha */}
          <div>
            <h3 className="text-sm font-bold text-blue-400 mb-3">🔗 Zerodha Kite Connect</h3>
            <div className="space-y-2">
              <input type="password" placeholder="API Key"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={zerodha.api_key} onChange={e => setZerodha(p => ({...p, api_key: e.target.value}))} />
              <input type="password" placeholder="API Secret"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={zerodha.api_secret} onChange={e => setZerodha(p => ({...p, api_secret: e.target.value}))} />
              <button onClick={() => saveKey.mutate({ provider: 'zerodha', ...zerodha })}
                className="px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded text-sm font-bold text-white">
                Save Zerodha Keys
              </button>
            </div>
          </div>

          {/* AI */}
          <div>
            <h3 className="text-sm font-bold text-purple-400 mb-3">🤖 AI Observer</h3>
            <div className="space-y-2">
              <select className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={ai.provider} onChange={e => setAi(p => ({...p, provider: e.target.value}))}>
                <option value="openai">OpenAI (GPT-4o)</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="gemini">Google (Gemini)</option>
              </select>
              <input type="password" placeholder="AI API Key"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white"
                value={ai.api_key} onChange={e => setAi(p => ({...p, api_key: e.target.value}))} />
              <button onClick={() => saveKey.mutate({ provider: ai.provider, api_key: ai.api_key })}
                className="px-4 py-2 bg-purple-700 hover:bg-purple-600 rounded text-sm font-bold text-white">
                Save AI Key
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
