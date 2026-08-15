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
      let detailMsg = 'Authentication failed — please try again'
      if (err?.response?.data?.detail) {
        const detail = err.response.data.detail
        detailMsg = typeof detail === 'string' ? detail : (detail.message || JSON.stringify(detail))
      } else if (err?.message) {
        detailMsg = err.message
      }
      setError(detailMsg)
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
    <div className="min-h-screen bg-gradient-to-b from-navy-950 via-navy-900 to-navy-950 text-navy-100 flex items-center justify-center p-4 lg:p-8 relative overflow-hidden font-sans">
      {/* Decorative Premium Glow Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />

      {/* Main Split-Screen Container */}
      <div className="w-full max-w-6xl relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        {/* Left Column: Sales & Product Feature Showcase (Visible on Large screens & nicely stacked on smaller) */}
        <div className="lg:col-span-7 flex flex-col justify-center space-y-6 pr-0 lg:pr-6 animate-fade-in">
          {/* Brand Badge & Header */}
          <div className="flex items-center space-x-3 mb-2">
            <div className="p-2.5 bg-navy-900/80 border border-navy-700 rounded-xl shadow-lg">
              <img src="/destiny-shield-icon.png" alt="Destiny Shield Icon" className="w-10 h-10 object-contain filter drop-shadow-[0_0_12px_rgba(245,158,11,0.6)]" />
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-white tracking-wider uppercase bg-gradient-to-r from-amber-200 via-amber-400 to-amber-500 bg-clip-text text-transparent">
                DESTINY
              </h1>
              <p className="text-xs text-navy-300">Automated Multi-User NIFTY Options Trading</p>
            </div>
          </div>

          {/* Hero Sales Pitch */}
          <div className="space-y-3">
            <h2 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight">
              Automate Your NIFTY Trading. <br />
              <span className="bg-gradient-to-r from-amber-300 via-orange-400 to-amber-500 bg-clip-text text-transparent">
                Maximize Execution & Consistency.
              </span>
            </h2>
            <p className="text-sm text-navy-300 leading-relaxed max-w-xl">
              Execute rule-based multi-user strategy signals on NIFTY options with zero delay, automated stop-loss management, and real-time execution tracking.
            </p>
          </div>

          {/* Live Performance / Metrics Preview Card */}
          <div className="bg-navy-900/70 border border-navy-700/80 rounded-2xl p-5 backdrop-blur-md shadow-xl grid grid-cols-3 gap-4">
            <div className="border-r border-navy-700/60 pr-2">
              <span className="text-[10px] uppercase font-bold text-navy-400 tracking-wider">Avg Execution</span>
              <p className="text-lg font-extrabold text-amber-400 mt-0.5">&lt; 150 ms</p>
              <span className="text-[10px] text-emerald-400 font-medium">⚡ Ultra-fast API</span>
            </div>
            <div className="border-r border-navy-700/60 pr-2">
              <span className="text-[10px] uppercase font-bold text-navy-400 tracking-wider">Strategy Mode</span>
              <p className="text-lg font-extrabold text-white mt-0.5">Multi-User</p>
              <span className="text-[10px] text-amber-400 font-medium">🛡️ Automated Risk</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-navy-400 tracking-wider">System Uptime</span>
              <p className="text-lg font-extrabold text-emerald-400 mt-0.5">99.9%</p>
              <span className="text-[10px] text-navy-300 font-medium">🟢 Live Monitored</span>
            </div>
          </div>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="flex items-start space-x-3 bg-navy-900/40 border border-navy-800 rounded-xl p-3">
              <div className="p-2 bg-orange-500/10 rounded-lg text-orange-400 mt-0.5">
                ⚡
              </div>
              <div>
                <h3 className="font-bold text-white">Rule-Based Automation</h3>
                <p className="text-navy-300 text-[11px]">Instant signal execution directly to broker accounts.</p>
              </div>
            </div>
            <div className="flex items-start space-x-3 bg-navy-900/40 border border-navy-800 rounded-xl p-3">
              <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400 mt-0.5">
                🛡️
              </div>
              <div>
                <h3 className="font-bold text-white">Multi-Account Management</h3>
                <p className="text-navy-300 text-[11px]">Seamlessly orchestrate multiple client portfolios.</p>
              </div>
            </div>
          </div>

          {/* Security & Trust Footer */}
          <div className="flex items-center space-x-6 pt-2 text-[11px] text-navy-400 border-t border-navy-800/80">
            <span className="flex items-center space-x-1.5">
              <span className="text-emerald-400">🔒</span>
              <span>256-bit Encrypted</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="text-amber-400">🔑</span>
              <span>Secure Token Auth</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="text-orange-400">📈</span>
              <span>NIFTY Options Optimized</span>
            </span>
          </div>
        </div>

        {/* Right Column: Existing Auth Container with Glassmorphic Card */}
        <div className="lg:col-span-5 w-full">
          <div className="bg-navy-900/70 backdrop-blur-xl border border-navy-700 rounded-2xl shadow-2xl p-6 sm:p-8 transition-all duration-300">
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
                  style={{ color: '#ffffff', backgroundColor: '#191e34' }}
                  className="w-full border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all duration-200"
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
                  style={{ color: '#ffffff', backgroundColor: '#191e34' }}
                  className="w-full border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all duration-200"
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
                    style={{ color: '#ffffff', backgroundColor: '#191e34' }}
                    className="w-full border border-navy-700 focus:border-orange-500/80 focus:ring-1 focus:ring-orange-500/50 rounded-xl px-4 py-3 text-sm focus:outline-none transition-all duration-200"
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

            {/* Divider */}
            <div className="relative my-6 text-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-navy-700/80" />
              </div>
              <span className="relative bg-navy-900/90 px-3 text-xs text-navy-400 uppercase tracking-wider">
                Or continue with
              </span>
            </div>

            {/* Google Sign-In Button */}
            <button
              type="button"
              onClick={() => {
                if (window.google?.accounts?.id) {
                  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '1069196179157-g2u1764tkr44mncgqkk33h2gedlif0ek.apps.googleusercontent.com'
                  window.google.accounts.id.initialize({
                    client_id: googleClientId,
                    callback: async (response: any) => {
                      if (response?.credential) {
                        setLoading(true)
                        setError('')
                        try {
                          const res = await sessionApi.googleLogin(response.credential)
                          sessionApi.setToken(res.access_token)
                          onLogin()
                        } catch (gErr: any) {
                          const msg = gErr?.response?.data?.detail || gErr?.message || 'Google authentication failed'
                          setError(msg)
                        } finally {
                          setLoading(false)
                        }
                      }
                    },
                  })
                  window.google.accounts.id.prompt()
                } else {
                  setError('Google Sign-In is loading. Please try again in a moment.')
                }
              }}
              className="w-full py-3 bg-navy-800 hover:bg-navy-750 active:scale-[0.98] border border-navy-700 rounded-xl text-sm font-semibold text-white flex items-center justify-center space-x-3 transition-all duration-200 shadow-md"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
              </svg>
              <span>Sign in with Google</span>
            </button>

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
    </div>
  )
}
