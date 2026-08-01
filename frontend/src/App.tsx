import { useState, useEffect } from 'react'
import { Dashboard } from './components/Dashboard/Dashboard'
import { Login } from './components/Login/Login'
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
    // Check session data immediately after logging in to fetch user profile attributes
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
  }

  // Loading state
  if (authenticated === null) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading PyramidStrategy...</div>
      </div>
    )
  }

  if (!authenticated) {
    return (
      <>
        <Login onLogin={handleLogin} />
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
