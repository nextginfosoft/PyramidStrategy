import { useState } from 'react'
import { sessionApi } from '../../services/api'

interface Props {
  onLogin: () => void
}

export function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isRegister, setIsRegister] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(false)

    if (isRegister && password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      if (isRegister) {
        await sessionApi.register(username, password)
        setSuccess('Account registered successfully! Signing in...')
        // Auto sign-in after successful registration
        setTimeout(async () => {
          try {
            const loginRes = await sessionApi.login(username, password)
            sessionApi.setToken(loginRes.access_token)
            onLogin()
          } catch (loginErr: any) {
            setError('Account created, but automatic sign-in failed. Please login manually.')
            setIsRegister(false)
            setConfirmPassword('')
          }
        }, 1500)
      } else {
        const res = await sessionApi.login(username, password)
        sessionApi.setToken(res.access_token)
        onLogin()
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Authentication failed — please try again')
    } finally {
      setLoading(false)
    }
  }

  const toggleMode = () => {
    setIsRegister(!isRegister)
    setError('')
    setSuccess('')
    setPassword('')
    setConfirmPassword('')
  }

  return (
    <div className="min-h-screen bg-navy-950 flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Decorative Premium Glow Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo / Header */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-block p-4 bg-navy-900/80 border border-navy-700 rounded-2xl shadow-xl mb-4">
            <span className="text-4xl filter drop-shadow-[0_0_10px_rgba(249,115,22,0.4)]">📐</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight bg-gradient-to-r from-orange-400 via-amber-200 to-violet-400 bg-clip-text text-transparent">
            PyramidStrategy
          </h1>
          <p className="text-sm text-navy-300 mt-2">Automated Multi-User NIFTY Options Trading</p>
        </div>

        {/* Auth Container with Glassmorphism */}
        <div className="bg-navy-900/60 backdrop-blur-xl border border-navy-700 rounded-2xl shadow-2xl p-8 transition-all duration-300">
          <h2 className="text-xl font-bold text-white mb-6 tracking-wide">
            {isRegister ? 'Create Account' : 'Sign In'}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-navy-300 uppercase tracking-wider mb-2">Username</label>
              <input
                type="text"
                placeholder="Enter username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-navy-800/80 border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none transition-all duration-200"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-navy-300 uppercase tracking-wider mb-2">Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-navy-800/80 border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none transition-all duration-200"
                required
              />
            </div>

            {isRegister && (
              <div>
                <label className="block text-xs font-semibold text-navy-300 uppercase tracking-wider mb-2">Confirm Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  className="w-full bg-navy-800/80 border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm text-white focus:outline-none transition-all duration-200"
                  required
                />
              </div>
            )}

            {error && (
              <div className="bg-red-950/30 border border-red-900/80 rounded-xl px-4 py-3 text-xs text-red-300 animate-shake">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-emerald-950/30 border border-emerald-900/80 rounded-xl px-4 py-3 text-xs text-emerald-300">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-400 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none rounded-xl text-sm font-bold text-white shadow-lg shadow-orange-600/20 transition-all duration-200"
            >
              {loading 
                ? (isRegister ? 'Creating Account...' : 'Signing in...') 
                : (isRegister ? 'Sign Up' : 'Sign In')}
            </button>
          </form>

          {/* Toggle Button */}
          <div className="mt-6 text-center border-t border-navy-700/80 pt-5">
            <button
              onClick={toggleMode}
              className="text-xs text-orange-400 hover:text-orange-300 font-medium transition-colors focus:outline-none"
            >
              {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
