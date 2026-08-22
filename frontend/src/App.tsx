import { useState, useEffect } from 'react'
import { Dashboard } from './components/Dashboard/Dashboard'
import { Login } from './components/Login/Login'
import { LandingPage } from './components/LandingPage/LandingPage'
import { SubscriptionModal } from './components/SubscriptionModal/SubscriptionModal'
import { sessionApi } from './services/api'
import { ToastContainer } from './components/Toast/Toast'
import { MotivationalToast } from './components/MotivationalToast/MotivationalToast'

export interface UserSession {
  username: string
  is_approved: boolean
  is_admin: boolean
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [user, setUser] = useState<UserSession | null>(null)
  const [view, setView] = useState<'landing' | 'login' | 'pricing'>('landing')
  const [showSubscriptionModal, setShowSubscriptionModal] = useState(false)

  useEffect(() => {
    // Check if we have a stored token
    const token = sessionApi.restoreToken()
    if (!token) {
      setAuthenticated(false)
      return
    }
    // Validate token with backend
    sessionApi.check()
      .then(res => {
        if (res.authenticated) {
          setAuthenticated(true)
          setUser({
            username: res.username,
            is_approved: res.is_approved,
            is_admin: res.is_admin
          })
        } else {
          setAuthenticated(false)
          setUser(null)
        }
      })
      .catch(() => {
        sessionApi.clearToken()
        setAuthenticated(false)
        setUser(null)
      })
  }, [])

  const handleLogin = () => {
    sessionApi.check()
      .then(res => {
        if (res.authenticated) {
          setAuthenticated(true)
          setUser({
            username: res.username,
            is_approved: res.is_approved,
            is_admin: res.is_admin
          })
        } else {
          setAuthenticated(false)
          setUser(null)
        }
      })
      .catch(() => {
        setAuthenticated(false)
        setUser(null)
      })
  }

  const handleLogout = () => {
    sessionApi.clearToken()
    setAuthenticated(false)
    setUser(null)
    setView('landing')
  }

  // Loading state
  if (authenticated === null) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading Destiny...</div>
      </div>
    )
  }

  if (!authenticated) {
    if (view === 'login') {
      return (
        <>
          <div className="min-h-screen bg-slate-950 relative">
            <button
              onClick={() => setView('landing')}
              className="absolute top-4 left-4 z-50 text-xs font-semibold text-slate-400 hover:text-white bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg transition-colors"
            >
              ← Back to Home
            </button>
            <Login onLogin={handleLogin} />
          </div>
          <ToastContainer />
          <MotivationalToast />
        </>
      )
    }

    return (
      <>
        <LandingPage
          onLoginClick={() => setView('login')}
          onRegisterClick={() => setView('login')}
          onViewPricingClick={() => setView('login')}
        />
        <SubscriptionModal
          isOpen={showSubscriptionModal}
          onClose={() => setShowSubscriptionModal(false)}
          onLoginRequired={() => {
            setShowSubscriptionModal(false)
            setView('login')
          }}
        />
        <ToastContainer />
        <MotivationalToast />
      </>
    )
  }

  return (
    <>
      <Dashboard user={user} onLogout={handleLogout} />
      <ToastContainer />
      <MotivationalToast />
    </>
  )
}
