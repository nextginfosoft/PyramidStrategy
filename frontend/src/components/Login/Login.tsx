import { useState } from 'react'
import { sessionApi } from '../../services/api'

interface Props {
  onLogin: () => void
}

export function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await sessionApi.login(username, password)
      sessionApi.setToken(res.access_token)
      onLogin()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Login failed — check credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo / Title */}
        <div className="text-center mb-8">
          <div className="text-4xl mb-2">📐</div>
          <h1 className="text-2xl font-bold text-white">PyramidStrategy</h1>
          <p className="text-sm text-gray-400 mt-1">Automated NIFTY Options Trading</p>
        </div>

        {/* Login Card */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <h2 className="text-lg font-bold text-white mb-4">Sign In</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-orange-500"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-orange-500"
                required
              />
            </div>

            {error && (
              <div className="bg-red-900/50 border border-red-700 rounded px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 rounded text-sm font-bold text-white transition-colors"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <p className="text-xs text-gray-600 text-center mt-4">
            Default: admin / pyramid123 — change in .env
          </p>
        </div>
      </div>
    </div>
  )
}
