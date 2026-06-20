import { useState, useEffect } from 'react'
import { Dashboard } from './components/Dashboard/Dashboard'
import { Login } from './components/Login/Login'
import { sessionApi } from './services/api'
import { ToastContainer } from './components/Toast/Toast'

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    // Check if we have a stored token
    const token = sessionApi.restoreToken()
    if (!token) {
      setAuthenticated(false)
      return
    }
    // Validate token with backend
    sessionApi.check()
      .then(res => setAuthenticated(res.authenticated))
      .catch(() => {
        sessionApi.clearToken()
        setAuthenticated(false)
      })
  }, [])

  const handleLogin = () => setAuthenticated(true)

  const handleLogout = () => {
    sessionApi.clearToken()
    setAuthenticated(false)
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
      </>
    )
  }

  return (
    <>
      <Dashboard onLogout={handleLogout} />
      <ToastContainer />
    </>
  )
}
