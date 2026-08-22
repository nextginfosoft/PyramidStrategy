import { useState, useEffect } from 'react'
import { adminApi, paymentsApi } from '../../services/api'
import { useToastStore } from '../../store/toastStore'

interface User {
  id: number
  username: string
  is_approved: boolean
  is_admin: boolean
  created_at?: string
}

interface UserLiveStatus {
  user_id: number
  username: string
  is_admin: boolean
  engine: {
    is_running: boolean
    paper_trade: boolean
    ce_state: string
    pe_state: string
    ce_lots: number
    pe_lots: number
    realized_pnl: number
    unrealized_pnl: number
  }
  kite: {
    authenticated: boolean
    ticker_connected: boolean
    last_nifty_tick: number | null
    last_api_error: string | null
    available_margin?: number | null
  }
}

interface Props {
  onClose: () => void
}

export function AdminPanel({ onClose }: Props) {
  const [activeTab, setActiveTab] = useState<'accounts' | 'monitoring' | 'gateway'>('accounts')
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [actionId, setActionId] = useState<number | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)

  // Razorpay Gateway Admin Config state
  const [rzpConfig, setRzpConfig] = useState({
    key_id: '',
    key_secret: '',
    webhook_secret: '',
    has_key_secret: false,
    has_webhook_secret: false,
    is_active: true
  })
  const [loadingRzp, setLoadingRzp] = useState(false)
  const [savingRzp, setSavingRzp] = useState(false)
  
  // Live monitoring states
  const [liveStatuses, setLiveStatuses] = useState<UserLiveStatus[]>([])
  const [refreshingLive, setRefreshingLive] = useState(false)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>('')

  // Add User Form states
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    isAdmin: false,
    zerodhaApiKey: '',
    zerodhaApiSecret: '',
    zerodhaUserId: '',
    zerodhaPassword: '',
    zerodhaTotpSecret: ''
  })

  // Analytics inspector states
  const [inspectUserId, setInspectUserId] = useState<number | null>(null)
  const [inspectUsername, setInspectUsername] = useState<string>('')
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [loadingAnalytics, setLoadingAnalytics] = useState(false)
  const [dateRange, setDateRange] = useState({
    start: new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10), // start of year
    end: new Date().toISOString().slice(0, 10)
  })

  const addToast = useToastStore(state => state.addToast)

  // Fetch registered users (Tab 1)
  const fetchUsers = async () => {
    try {
      setLoading(true)
      const data = await adminApi.getUsers()
      setUsers(data)
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Failed to load users', 'error')
    } finally {
      setLoading(false)
    }
  }

  // Fetch live engine/kite status (Tab 2)
  const fetchLiveStatuses = async (showPulse = false) => {
    try {
      if (showPulse) setRefreshingLive(true)
      const data = await adminApi.getUsersStatus()
      setLiveStatuses(data)
      setLastRefreshedAt(new Date().toLocaleTimeString())
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Failed to load live status', 'error')
    } finally {
      if (showPulse) setRefreshingLive(false)
    }
  }

  // Poll live statuses when Tab 2 is active
  useEffect(() => {
    if (activeTab === 'accounts') {
      fetchUsers()
    } else {
      fetchLiveStatuses(true)
      const interval = setInterval(() => {
        fetchLiveStatuses(false)
      }, 3000) // Poll every 3 seconds for real-time responsiveness
      return () => clearInterval(interval)
    }
  }, [activeTab])

  // Approve / Suspend User
  const handleApprove = async (id: number) => {
    setActionId(id)
    try {
      const data = await adminApi.approveUser(id)
      addToast(
        `User approval status updated: ${data.is_approved ? 'APPROVED' : 'SUSPENDED'}`,
        'success'
      )
      setUsers(prev =>
        prev.map(u => (u.id === id ? { ...u, is_approved: data.is_approved } : u))
      )
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Action failed', 'error')
    } finally {
      setActionId(null)
    }
  }

  // Promote / Revoke Admin
  const handleToggleAdmin = async (id: number) => {
    setActionId(id)
    try {
      const data = await adminApi.toggleAdmin(id)
      addToast(
        `User role updated: ${data.is_admin ? 'PROMOTED TO ADMIN' : 'REVOKED ADMIN'}`,
        'success'
      )
      setUsers(prev =>
        prev.map(u => (u.id === id ? { ...u, is_admin: data.is_admin } : u))
      )
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Action failed', 'error')
    } finally {
      setActionId(null)
    }
  }

  // Test Zerodha API credentials
  const handleTestCredentials = async (id: number) => {
    setTestingId(id)
    try {
      addToast('Testing broker credentials, please wait...', 'info')
      const data = await adminApi.testCredentials(id)
      if (data.status === 'success') {
        addToast(`✅ ${data.message || 'Zerodha credentials verified successfully!'}`, 'success')
      } else {
        addToast(`❌ Connection Failed: ${data.message || 'Invalid response'}`, 'error')
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'API connection test failed'
      addToast(`❌ Connection Failed: ${errorMsg}`, 'error')
    } finally {
      setTestingId(null)
    }
  }

  // Delete User
  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`⚠️ WARNING: Are you sure you want to delete and purge user "${name}"?\nThis will completely erase all their configs, trades, and logs. This cannot be undone.`)) {
      return
    }
    setActionId(id)
    try {
      await adminApi.deleteUser(id)
      addToast(`User "${name}" has been deleted and purged.`, 'success')
      setUsers(prev => prev.filter(u => u.id !== id))
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Deletion failed', 'error')
    } finally {
      setActionId(null)
    }
  }

  // Submit User Registration
  const handleRegisterUser = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await adminApi.createUser({
        username: formData.username,
        password: formData.password,
        is_admin: formData.isAdmin,
        zerodha_api_key: formData.zerodhaApiKey || null,
        zerodha_api_secret: formData.zerodhaApiSecret || null,
        zerodha_username: formData.zerodhaUserId || null,
        zerodha_password: formData.zerodhaPassword || null,
        zerodha_totp_secret: formData.zerodhaTotpSecret || null,
      })
      addToast(`Trader "${formData.username}" created successfully!`, 'success')
      setShowAddForm(false)
      // Reset form
      setFormData({
        username: '',
        password: '',
        isAdmin: false,
        zerodhaApiKey: '',
        zerodhaApiSecret: '',
        zerodhaUserId: '',
        zerodhaPassword: '',
        zerodhaTotpSecret: ''
      })
      fetchUsers()
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Failed to create user', 'error')
    }
  }

  // Fetch individual analytics for inspection popup
  const fetchUserAnalytics = async (userId: number, username: string) => {
    setInspectUserId(userId)
    setInspectUsername(username)
    setLoadingAnalytics(true)
    try {
      const data = await adminApi.getUserAnalytics(userId, dateRange.start, dateRange.end)
      setAnalyticsData(data)
    } catch (err: any) {
      addToast(err.response?.data?.detail || err.message || 'Failed to load user analytics', 'error')
    } finally {
      setLoadingAnalytics(false)
    }
  }

  // Fetch Razorpay Admin Configuration
  const fetchRzpConfig = async () => {
    try {
      setLoadingRzp(true)
      const data = await paymentsApi.getAdminConfig()
      setRzpConfig({
        key_id: data.key_id || '',
        key_secret: data.has_key_secret ? '******' : '',
        webhook_secret: data.has_webhook_secret ? '******' : '',
        has_key_secret: data.has_key_secret,
        has_webhook_secret: data.has_webhook_secret,
        is_active: data.is_active ?? true
      })
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'Failed to load Razorpay config', 'error')
    } finally {
      setLoadingRzp(false)
    }
  }

  // Save Razorpay Admin Configuration
  const handleSaveRzpConfig = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSavingRzp(true)
      await paymentsApi.updateAdminConfig({
        key_id: rzpConfig.key_id,
        key_secret: rzpConfig.key_secret,
        webhook_secret: rzpConfig.webhook_secret,
        is_active: rzpConfig.is_active
      })
      addToast('✅ Razorpay API credentials saved successfully!', 'success')
      fetchRzpConfig()
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'Failed to save Razorpay config', 'error')
    } finally {
      setSavingRzp(false)
    }
  }

  // Reload analytics when date filters change
  useEffect(() => {
    if (inspectUserId) {
      fetchUserAnalytics(inspectUserId, inspectUsername)
    }
  }, [dateRange.start, dateRange.end])

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-5xl bg-navy-950/95 border border-navy-500/25 rounded-2xl p-6 shadow-2xl overflow-hidden flex flex-col max-h-[88vh] text-white">
        {/* Glowing background spotlights */}
        <div className="absolute -top-32 -left-32 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-32 -right-32 w-80 h-80 bg-purple-500/5 rounded-full blur-3xl" />

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-navy-800 pb-4 mb-5 z-10">
          <div className="flex items-center gap-2.5">
            <span aria-hidden="true" className="text-2xl">🛡️</span>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide">Administrator Command Center</h2>
              <p className="text-xs text-navy-300">Moderate trading accounts, monitor Zerodha terminals, and audit P&L statistics.</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 bg-navy-900 hover:bg-navy-850 rounded-lg text-navy-300 hover:text-white transition active:scale-95 border border-navy-800"
            title="Close command center"
          >
            ✕
          </button>
        </div>

        {/* Tabs Bar */}
        <div className="flex justify-between items-center mb-4 z-10 border-b border-navy-900 pb-2">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('accounts')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all border ${
                activeTab === 'accounts' 
                  ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' 
                  : 'bg-transparent text-navy-300 border-transparent hover:text-white'
              }`}
            >
              👤 Accounts Control
            </button>
            <button
              onClick={() => setActiveTab('monitoring')}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all border ${
                activeTab === 'monitoring' 
                  ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' 
                  : 'bg-transparent text-navy-300 border-transparent hover:text-white'
              }`}
            >
              📊 Live Status & P&L Monitor
            </button>
            <button
              onClick={() => {
                setActiveTab('gateway')
                fetchRzpConfig()
              }}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all border ${
                activeTab === 'gateway' 
                  ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30' 
                  : 'bg-transparent text-navy-300 border-transparent hover:text-white'
              }`}
            >
              💳 Razorpay Gateway Keys
            </button>
          </div>

          {activeTab === 'accounts' && (
            <button
              onClick={() => setShowAddForm(true)}
              className="py-1.5 px-4 bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold rounded-lg text-xs transition active:scale-95 flex items-center gap-1.5"
            >
              ➕ Register New Trader
            </button>
          )}

          {activeTab === 'monitoring' && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-navy-450 font-mono select-none">
                Auto-refreshed: {lastRefreshedAt}
              </span>
              <button
                onClick={() => fetchLiveStatuses(true)}
                disabled={refreshingLive}
                className="py-1 px-3 bg-navy-900 hover:bg-navy-850 text-navy-300 rounded-lg text-xs transition active:scale-95 border border-navy-800 flex items-center gap-1.5"
              >
                {refreshingLive ? (
                  <div className="w-3.5 h-3.5 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                ) : '🔄'}
              </button>
            </div>
          )}
        </div>

        {/* Modal Scroll Content */}
        <div className="flex-1 overflow-y-auto min-h-0 z-10 pr-1">
          {activeTab === 'accounts' ? (
            /* ==================== TAB 1: ACCOUNTS CONTROL ==================== */
            loading ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-navy-300 font-medium">Fetching registered users...</p>
              </div>
            ) : users.length === 0 ? (
              <div className="text-center py-20 text-navy-400">
                <span className="text-3xl block mb-2">👥</span>
                No registered traders found in system database.
              </div>
            ) : (
              <div className="overflow-x-auto border border-navy-800/80 rounded-xl bg-navy-900/30 shadow-inner">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-navy-950/70 border-b border-navy-800 text-[10px] font-extrabold text-navy-400 uppercase tracking-widest select-none">
                      <th className="py-3 px-4">User ID</th>
                      <th className="py-3 px-4">Username</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-center">Role</th>
                      <th className="py-3 px-4 text-center">Command Operations</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-850/60 text-xs">
                    {users.map(user => {
                      const isBusy = actionId === user.id
                      const isTesting = testingId === user.id
                      return (
                        <tr key={user.id} className="hover:bg-navy-850/20 transition-colors duration-150">
                          <td className="py-3 px-4 font-mono text-navy-400">#{user.id}</td>
                          <td className="py-3 px-4 font-bold text-white select-all">{user.username}</td>
                          <td className="py-3 px-4 text-center">
                            {user.is_approved ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 font-bold text-[10px] uppercase select-none">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/25 text-amber-400 font-bold text-[10px] uppercase select-none">
                                Pending
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-center">
                            {user.is_admin ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/25 text-cyan-400 font-bold text-[10px] uppercase select-none">
                                👑 Admin
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-navy-850 border border-navy-750 text-navy-300 font-bold text-[10px] uppercase select-none">
                                Trader
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <div className="flex items-center justify-center gap-2">
                              {/* Approve/Suspend */}
                              <button
                                onClick={() => handleApprove(user.id)}
                                disabled={isBusy || isTesting}
                                className={`py-1 px-2.5 rounded-lg text-[10px] font-bold tracking-wider uppercase transition active:scale-95 ${
                                  user.is_approved 
                                    ? 'bg-amber-950/20 hover:bg-amber-900/30 text-amber-400 border border-amber-500/20' 
                                    : 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30'
                                }`}
                              >
                                {user.is_approved ? 'Suspend' : 'Approve'}
                              </button>
                              
                              {/* Test API Credentials */}
                              <button
                                onClick={() => handleTestCredentials(user.id)}
                                disabled={isBusy || isTesting}
                                className="py-1 px-2.5 bg-indigo-950/20 hover:bg-indigo-900/30 text-indigo-400 border border-indigo-500/20 rounded-lg text-[10px] font-bold tracking-wider uppercase transition active:scale-95 flex items-center gap-1"
                              >
                                {isTesting ? (
                                  <div className="w-2.5 h-2.5 border border-indigo-400 border-t-transparent rounded-full animate-spin" />
                                ) : '🔌'}
                                Test API
                              </button>
                              
                              {/* Toggle Admin */}
                              <button
                                onClick={() => handleToggleAdmin(user.id)}
                                disabled={isBusy || isTesting}
                                className={`py-1 px-2.5 rounded-lg text-[10px] font-bold tracking-wider uppercase border transition active:scale-95 ${
                                  user.is_admin
                                    ? 'bg-purple-950/20 hover:bg-purple-900/30 text-purple-400 border-purple-500/20'
                                    : 'bg-cyan-500/10 hover:bg-cyan-500/25 text-cyan-400 border-cyan-500/25'
                                }`}
                              >
                                {user.is_admin ? 'Revoke Admin' : 'Make Admin'}
                              </button>

                              {/* Delete Account */}
                              <button
                                onClick={() => handleDelete(user.id, user.username)}
                                disabled={isBusy || isTesting}
                                className="py-1 px-2 bg-red-950/25 hover:bg-red-900/30 text-red-400 border border-red-500/20 rounded-lg text-[10px] font-bold tracking-wider uppercase transition active:scale-95"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          ) : activeTab === 'monitoring' ? (
            /* ==================== TAB 2: LIVE MONITOR & P&L ==================== */
            liveStatuses.length === 0 ? (
              <div className="text-center py-20 text-navy-400">
                <span className="text-4xl block mb-2">📡</span>
                No approved traders online.
              </div>
            ) : (
              <div className="space-y-6">
                {/* Aggregate stats summary box */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Card 1: Total Accounts */}
                  <div className="p-4 bg-navy-900/40 backdrop-blur-md border border-navy-800/80 rounded-xl hover:-translate-y-0.5 transition-all duration-200 shadow-lg shadow-navy-950/40 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-navy-400 uppercase font-extrabold tracking-widest block mb-1">Total Traders</span>
                      <span className="text-2xl font-black text-white font-mono select-none">{liveStatuses.length}</span>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-lg">
                      👥
                    </div>
                  </div>

                  {/* Card 2: Active Engines */}
                  <div className="p-4 bg-navy-900/40 backdrop-blur-md border border-navy-800/80 rounded-xl hover:-translate-y-0.5 transition-all duration-200 shadow-lg shadow-navy-950/40 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-navy-400 uppercase font-extrabold tracking-widest block mb-1">Active Engines</span>
                      <span className="text-2xl font-black text-cyan-400 font-mono select-none">
                        {liveStatuses.filter(x => x.engine.is_running).length}
                      </span>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 text-lg">
                      ⚙️
                    </div>
                  </div>

                  {/* Card 3: Active Kite Sessions */}
                  <div className="p-4 bg-navy-900/40 backdrop-blur-md border border-navy-800/80 rounded-xl hover:-translate-y-0.5 transition-all duration-200 shadow-lg shadow-navy-950/40 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-navy-400 uppercase font-extrabold tracking-widest block mb-1">Kite Feeds</span>
                      <span className="text-2xl font-black text-emerald-400 font-mono select-none">
                        {liveStatuses.filter(x => x.kite.authenticated && x.kite.ticker_connected).length}
                      </span>
                    </div>
                    <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 text-lg">
                      📡
                    </div>
                  </div>

                  {/* Card 4: Net Combined P&L */}
                  {(() => {
                    const netPnl = liveStatuses.reduce((acc, u) => acc + u.engine.realized_pnl, 0)
                    const isPositive = netPnl >= 0
                    return (
                      <div className={`p-4 bg-navy-900/40 backdrop-blur-md border rounded-xl hover:-translate-y-0.5 transition-all duration-200 shadow-lg shadow-navy-950/40 flex items-center justify-between ${
                        isPositive ? 'border-emerald-500/20 shadow-emerald-950/5' : 'border-rose-500/20 shadow-rose-950/5'
                      }`}>
                        <div>
                          <span className="text-[10px] text-navy-400 uppercase font-extrabold tracking-widest block mb-1">Total P&L Today</span>
                          <span className={`text-xl font-black font-mono select-none ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {isPositive ? '+' : ''}₹{netPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg ${
                          isPositive ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                        }`}>
                          {isPositive ? '📈' : '📉'}
                        </div>
                      </div>
                    )
                  })()}
                </div>

                {/* Grid Monitor Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-1">
                  {liveStatuses.map(user => {
                    const isKiteConnected = user.kite.authenticated && user.kite.ticker_connected
                    const totalPnl = user.engine.realized_pnl
                    const unRealPnl = user.engine.unrealized_pnl
                    const isEngineRunning = user.engine.is_running
                    const isPaperTrade = user.engine.paper_trade
                    const initial = user.username.charAt(0).toUpperCase()

                    return (
                      <div 
                        key={user.user_id} 
                        className={`relative p-4 rounded-2xl transition-all duration-300 border flex flex-col justify-between gap-3.5 bg-gradient-to-b shadow-lg ${
                          isEngineRunning
                            ? isPaperTrade
                              ? 'from-navy-900/60 to-navy-950/40 border-yellow-500/20 border-l-4 border-l-yellow-500 hover:border-yellow-500/40 shadow-yellow-950/10'
                              : 'from-navy-900/60 to-navy-950/40 border-cyan-500/20 border-l-4 border-l-cyan-500 hover:border-cyan-500/40 shadow-cyan-950/10'
                            : 'from-navy-900/40 to-navy-950/20 border-navy-850 border-l-4 border-l-navy-700 hover:border-navy-700/80 shadow-navy-950/20'
                        }`}
                      >
                        {/* Card Header */}
                        <div className="flex items-center justify-between border-b border-navy-850/40 pb-2.5">
                          <div className="flex items-center gap-2.5">
                            {/* Profile Initial Avatar with Live pulse dot */}
                            <div className="relative">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-black text-xs border uppercase select-none shadow-inner ${
                                isEngineRunning 
                                  ? isPaperTrade 
                                    ? 'bg-gradient-to-br from-yellow-500/20 to-amber-500/10 border-yellow-500/30 text-yellow-400'
                                    : 'bg-gradient-to-br from-cyan-500/20 to-indigo-500/10 border-cyan-500/30 text-cyan-400'
                                  : 'bg-navy-800 border-navy-700 text-navy-400'
                              }`}>
                                {initial}
                              </div>
                              <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-navy-950 ${
                                isKiteConnected ? 'bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400/50' : 'bg-rose-500'
                              }`} />
                            </div>
                            
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="font-bold text-white text-xs select-all truncate max-w-[85px]">{user.username}</span>
                                {user.is_admin && (
                                  <span className="text-[7px] bg-purple-950 border border-purple-500/30 text-purple-400 px-1 py-0.5 rounded font-black uppercase tracking-wider scale-90 select-none">
                                    ADM
                                  </span>
                                )}
                              </div>
                              <span className="text-[9px] text-navy-500 select-none font-mono tracking-wider">CLIENT #{user.user_id}</span>
                            </div>
                          </div>

                          <button
                            onClick={() => fetchUserAnalytics(user.user_id, user.username)}
                            className="py-1 px-2.5 bg-gradient-to-r from-navy-950 to-navy-900 hover:from-cyan-950 hover:to-navy-900 border border-navy-800 hover:border-cyan-500/40 text-cyan-400 rounded-lg text-[9px] font-extrabold uppercase transition duration-150 active:scale-95 flex items-center gap-0.5 shadow-md shadow-navy-950/40"
                          >
                            📊 Analysis
                          </button>
                        </div>

                        {/* Card Body - Inline status & margin info */}
                        <div className="flex justify-between items-center text-[10px] gap-2 select-none">
                          {/* Engine Mode Status */}
                          <div>
                            {isEngineRunning ? (
                              <span className={`inline-flex items-center px-2 py-0.5 rounded font-extrabold text-[8px] uppercase tracking-wider ${
                                isPaperTrade 
                                  ? 'bg-yellow-500/10 border border-yellow-500/25 text-yellow-500' 
                                  : 'bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 shadow-sm shadow-cyan-950/20'
                              }`}>
                                {isPaperTrade ? '⚡ PAPER MODE' : '🔥 LIVE MODE'}
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-navy-850 text-navy-450 border border-navy-800/80 text-[8px] font-extrabold uppercase tracking-wider">
                                ENGINE STOPPED
                              </span>
                            )}
                          </div>
                          
                          {/* Fund Balance */}
                          {user.kite.available_margin != null ? (
                            <span className="font-mono font-bold text-[10px] text-cyan-400 bg-cyan-950/40 border border-cyan-500/20 px-2 py-0.5 rounded-lg shadow-inner">
                              ₹{user.kite.available_margin.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </span>
                          ) : (
                            <span className="text-navy-600 font-mono text-[10px]">—</span>
                          )}
                        </div>

                        {/* Card Body - Positions section (extremely refined) */}
                        <div className="bg-navy-950/40 border border-navy-850/60 p-2.5 rounded-xl flex flex-col gap-1.5 min-h-[46px] justify-center shadow-inner">
                          {user.engine.ce_lots > 0 || user.engine.pe_lots > 0 ? (
                            <div className="flex flex-col gap-1 select-none">
                              {user.engine.ce_lots > 0 && (
                                <div className="flex justify-between items-center text-[9px] font-mono bg-emerald-950/30 border border-emerald-500/10 rounded-md px-2 py-0.5">
                                  <span className="text-emerald-400 font-bold">🟢 CALL (CE)</span>
                                  <span className="text-emerald-400 font-black tracking-wide">{user.engine.ce_lots} Lots ({user.engine.ce_state})</span>
                                </div>
                              )}
                              {user.engine.pe_lots > 0 && (
                                <div className="flex justify-between items-center text-[9px] font-mono bg-rose-950/30 border border-rose-500/10 rounded-md px-2 py-0.5">
                                  <span className="text-rose-400 font-bold">🔴 PUT (PE)</span>
                                  <span className="text-rose-400 font-black tracking-wide">{user.engine.pe_lots} Lots ({user.engine.pe_state})</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center justify-center gap-1 text-navy-500 text-[10px] font-medium tracking-wide">
                              <span className="text-[11px] opacity-70">🔒</span> No active positions
                            </div>
                          )}
                        </div>

                        {/* Card Footer - P&L side by side with neon glow effect */}
                        <div className="grid grid-cols-2 border-t border-navy-850/40 pt-2.5 text-[10px]">
                          {/* Realized */}
                          <div className="flex flex-col select-none pr-1">
                            <span className="text-[8px] text-navy-500 font-extrabold uppercase tracking-wider">Realized P&L</span>
                            <span className={`font-mono font-black select-all truncate ${
                              totalPnl >= 0 
                                ? 'text-emerald-400 drop-shadow-[0_0_6px_rgba(16,185,129,0.25)]' 
                                : 'text-rose-400 drop-shadow-[0_0_6px_rgba(239,68,68,0.25)]'
                            }`}>
                              {totalPnl >= 0 ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </span>
                          </div>

                          {/* Unrealized */}
                          <div className="flex flex-col select-none pl-2.5 border-l border-navy-850/40">
                            <span className="text-[8px] text-navy-500 font-extrabold uppercase tracking-wider">Unrealized P&L</span>
                            <span className={`font-mono font-black select-all truncate ${
                              unRealPnl >= 0 
                                ? 'text-emerald-400 drop-shadow-[0_0_6px_rgba(16,185,129,0.25)]' 
                                : 'text-rose-400 drop-shadow-[0_0_6px_rgba(239,68,68,0.25)]'
                            }`}>
                              {unRealPnl >= 0 ? '+' : ''}₹{unRealPnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                            </span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          ) : (
            /* Tab 3: Razorpay Gateway Keys */
            <div className="flex-1 overflow-y-auto min-h-0 pr-1 space-y-6">
              <div className="p-5 bg-navy-900/40 border border-navy-800 rounded-xl space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-indigo-400">💳 Razorpay Payment Gateway Configuration</h3>
                  <p className="text-xs text-navy-400 mt-1">
                    Enter your Razorpay Test API Keys (`rzp_test_...`) or Live API Keys (`rzp_live_...`). These credentials will dynamically power subscriber checkouts across the application.
                  </p>
                </div>

                {loadingRzp ? (
                  <div className="py-8 flex justify-center">
                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : (
                  <form onSubmit={handleSaveRzpConfig} className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-navy-300 mb-1">Razorpay Key ID</label>
                      <input
                        type="text"
                        value={rzpConfig.key_id}
                        onChange={e => setRzpConfig(prev => ({ ...prev, key_id: e.target.value }))}
                        placeholder="rzp_test_xxxxxxxx or rzp_live_xxxxxxxx"
                        className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-navy-300 mb-1">Razorpay Key Secret</label>
                      <input
                        type="password"
                        value={rzpConfig.key_secret}
                        onChange={e => setRzpConfig(prev => ({ ...prev, key_secret: e.target.value }))}
                        placeholder={rzpConfig.has_key_secret ? '•••••••••••• (Leave blank to keep existing secret)' : 'Enter Razorpay Key Secret'}
                        className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-navy-300 mb-1">Razorpay Webhook Secret (Optional)</label>
                      <input
                        type="password"
                        value={rzpConfig.webhook_secret}
                        onChange={e => setRzpConfig(prev => ({ ...prev, webhook_secret: e.target.value }))}
                        placeholder={rzpConfig.has_webhook_secret ? '•••••••••••• (Leave blank to keep existing secret)' : 'Enter Webhook Secret'}
                        className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-indigo-500"
                      />
                    </div>

                    <div className="pt-2 flex justify-end">
                      <button
                        type="submit"
                        disabled={savingRzp}
                        className="py-2.5 px-6 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-md transition disabled:opacity-50"
                      >
                        {savingRzp ? 'Saving Gateway Settings...' : 'Save Credentials'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* SUB-MODAL 1: Register User Form Overlay */}
      {showAddForm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/85 backdrop-blur-sm" onClick={() => setShowAddForm(false)} />
          <div className="relative w-full max-w-2xl bg-navy-950 border border-navy-500/30 rounded-xl p-5 shadow-2xl z-[70] text-white overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-navy-800 pb-3 mb-4">
              <h3 className="text-sm font-black text-cyan-400 uppercase tracking-widest flex items-center gap-1.5 select-none">
                👤 Register New System Trader
              </h3>
              <button 
                onClick={() => setShowAddForm(false)}
                className="p-1 text-navy-400 hover:text-white transition"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRegisterUser} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Left Column: Dashboard System Account */}
                <div className="space-y-3.5 bg-navy-900/50 p-4 border border-navy-900 rounded-xl">
                  <h4 className="text-[10px] font-black text-indigo-400 uppercase tracking-widest border-b border-navy-800 pb-1 mb-2 select-none">
                    1. System Credentials
                  </h4>
                  <div>
                    <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">Traders Username</label>
                    <input
                      type="text"
                      required
                      value={formData.username}
                      onChange={e => setFormData(prev => ({ ...prev, username: e.target.value }))}
                      className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                      placeholder="e.g. janesmith"
                    />
                  </div>
                  <div>
                    <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">Dashboard Password</label>
                    <input
                      type="password"
                      required
                      value={formData.password}
                      onChange={e => setFormData(prev => ({ ...prev, password: e.target.value }))}
                      className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="flex items-center gap-2 pt-2 select-none">
                    <input
                      type="checkbox"
                      id="isAdmin"
                      checked={formData.isAdmin}
                      onChange={e => setFormData(prev => ({ ...prev, isAdmin: e.target.checked }))}
                      className="w-4 h-4 bg-navy-950 border-navy-800 rounded text-cyan-500 focus:ring-cyan-500 cursor-pointer"
                    />
                    <label htmlFor="isAdmin" className="font-bold text-navy-300 cursor-pointer">
                      Grant System Administrator Status
                    </label>
                  </div>
                </div>

                {/* Right Column: Zerodha API Integration */}
                <div className="space-y-3.5 bg-navy-900/50 p-4 border border-navy-900 rounded-xl">
                  <h4 className="text-[10px] font-black text-amber-500 uppercase tracking-widest border-b border-navy-800 pb-1 mb-2 select-none">
                    2. Zerodha Integration
                  </h4>
                  <div>
                    <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">Kite Client ID (User ID)</label>
                    <input
                      type="text"
                      value={formData.zerodhaUserId}
                      onChange={e => setFormData(prev => ({ ...prev, zerodhaUserId: e.target.value }))}
                      className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500 font-mono"
                      placeholder="e.g. AB1234"
                    />
                  </div>
                  <div>
                    <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">Kite Password</label>
                    <input
                      type="password"
                      value={formData.zerodhaPassword}
                      onChange={e => setFormData(prev => ({ ...prev, zerodhaPassword: e.target.value }))}
                      className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                      placeholder="••••••••"
                    />
                  </div>
                  <div>
                    <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">TOTP Secret Key (2FA)</label>
                    <input
                      type="password"
                      value={formData.zerodhaTotpSecret}
                      onChange={e => setFormData(prev => ({ ...prev, zerodhaTotpSecret: e.target.value }))}
                      className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500 font-mono"
                      placeholder="e.g. GZ3V8BJK4X109S"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">API Key</label>
                      <input
                        type="password"
                        value={formData.zerodhaApiKey}
                        onChange={e => setFormData(prev => ({ ...prev, zerodhaApiKey: e.target.value }))}
                        className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500 font-mono"
                        placeholder="Key"
                      />
                    </div>
                    <div>
                      <label className="block text-navy-450 font-bold mb-1 uppercase tracking-wide">API Secret</label>
                      <input
                        type="password"
                        value={formData.zerodhaApiSecret}
                        onChange={e => setFormData(prev => ({ ...prev, zerodhaApiSecret: e.target.value }))}
                        className="w-full px-3 py-2 bg-navy-950 border border-navy-800 rounded-lg text-white focus:outline-none focus:border-cyan-500 font-mono"
                        placeholder="Secret"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-navy-900">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="py-2 px-4 bg-navy-900 hover:bg-navy-850 border border-navy-800 rounded-lg text-navy-300 font-bold tracking-wide uppercase transition duration-150 active:scale-95"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="py-2 px-5 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 text-navy-950 font-black tracking-wide uppercase rounded-lg transition duration-150 active:scale-95 shadow-md shadow-cyan-950/20"
                >
                  Create Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUB-MODAL 2: User Historical Analytics Inspector */}
      {inspectUserId !== null && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/85 backdrop-blur-sm" onClick={() => setInspectUserId(null)} />
          <div className="relative w-full max-w-4xl bg-navy-950 border border-navy-500/30 rounded-2xl p-5 shadow-2xl z-[70] text-white overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between border-b border-navy-800 pb-3 mb-4">
              <div>
                <h3 className="text-sm font-black text-cyan-400 uppercase tracking-widest flex items-center gap-1.5">
                  📊 Performance Inspection: {inspectUsername}
                </h3>
                <p className="text-[10px] text-navy-400 font-medium">Audit historical P&L logs, drawdown details, and win rate diagnostics.</p>
              </div>
              <button 
                onClick={() => setInspectUserId(null)}
                className="p-1.5 bg-navy-900 hover:bg-navy-850 rounded-lg text-navy-300 hover:text-white transition border border-navy-800"
              >
                ✕
              </button>
            </div>

            {/* Date Filters Row */}
            <div className="flex flex-wrap items-center gap-3 p-3 bg-navy-900/40 border border-navy-900 rounded-xl mb-4 text-xs select-none">
              <span className="font-bold text-navy-300 uppercase tracking-wide">Audit Period:</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="date"
                  value={dateRange.start}
                  onChange={e => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                  className="px-2 py-1 bg-navy-950 border border-navy-800 rounded text-white font-mono"
                />
                <span className="text-navy-500 font-bold">to</span>
                <input
                  type="date"
                  value={dateRange.end}
                  onChange={e => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                  className="px-2 py-1 bg-navy-950 border border-navy-800 rounded text-white font-mono"
                />
              </div>
            </div>

            {/* Scrollable Modal Content */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-1 space-y-5">
              {loadingAnalytics ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3">
                  <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs text-navy-300 font-medium">Assembling audit ledger...</p>
                </div>
              ) : !analyticsData ? (
                <div className="text-center py-20 text-navy-450 italic">
                  Failed to fetch audit data for this trader.
                </div>
              ) : (
                <>
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 bg-navy-900/30 border border-navy-900 rounded-xl">
                      <span className="text-[9px] text-navy-500 font-extrabold uppercase tracking-wider block mb-0.5">Total Net Profit</span>
                      <span className={`text-base font-black font-mono ${analyticsData.summary.total_net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {analyticsData.summary.total_net_pnl >= 0 ? '+' : ''}₹{analyticsData.summary.total_net_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="p-3 bg-navy-900/30 border border-navy-900 rounded-xl">
                      <span className="text-[9px] text-navy-500 font-extrabold uppercase tracking-wider block mb-0.5">Win Rate (Days)</span>
                      <span className="text-base font-black text-cyan-400 font-mono">
                        {analyticsData.summary.win_rate}% <span className="text-[9px] text-navy-400 font-normal">({analyticsData.summary.winning_days}/{analyticsData.summary.total_days}d)</span>
                      </span>
                    </div>
                    <div className="p-3 bg-navy-900/30 border border-navy-900 rounded-xl">
                      <span className="text-[9px] text-navy-500 font-extrabold uppercase tracking-wider block mb-0.5">Paid Brokerage</span>
                      <span className="text-base font-black text-amber-500 font-mono">
                        ₹{analyticsData.summary.total_brokerage.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="p-3 bg-navy-900/30 border border-navy-900 rounded-xl">
                      <span className="text-[9px] text-navy-500 font-extrabold uppercase tracking-wider block mb-0.5">Max Net Drawdown</span>
                      <span className="text-base font-black text-rose-400 font-mono">
                        ₹{analyticsData.summary.max_drawdown.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  {/* Daily Ledger Table */}
                  <div className="space-y-2">
                    <h4 className="text-[10px] font-black text-navy-400 uppercase tracking-widest select-none">
                      Daily Ledger Sheet
                    </h4>
                    {analyticsData.daily_data.length === 0 ? (
                      <div className="text-center py-10 bg-navy-900/20 border border-navy-900 rounded-xl text-navy-500 italic select-none">
                        No trade execution records found for the selected period.
                      </div>
                    ) : (
                      <div className="overflow-x-auto border border-navy-900 rounded-xl bg-navy-900/20 shadow-inner">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="bg-navy-950/70 border-b border-navy-900 text-[9px] font-black text-navy-500 uppercase tracking-widest select-none">
                              <th className="py-2.5 px-3">Trade Date</th>
                              <th className="py-2.5 px-3 text-right">Gross Profit</th>
                              <th className="py-2.5 px-3 text-right">Brokerage</th>
                              <th className="py-2.5 px-3 text-right">Net Profit</th>
                              <th className="py-2.5 px-3 text-center">Trades (Won/Total)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-navy-850/40 font-mono">
                            {analyticsData.daily_data.map((r: any) => (
                              <tr key={r.date} className="hover:bg-navy-850/15 transition-colors duration-150">
                                <td className="py-2.5 px-3 font-sans text-white font-semibold select-all">{r.date}</td>
                                <td className={`py-2.5 px-3 text-right font-bold ${r.gross_pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                  ₹{r.gross_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                                <td className="py-2.5 px-3 text-right text-amber-500 font-bold">
                                  ₹{r.brokerage.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                                <td className={`py-2.5 px-3 text-right font-black ${r.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  ₹{r.net_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                                <td className="py-2.5 px-3 text-center text-navy-300 font-sans">
                                  {r.winning_trades} / {r.total_trades}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            
            <div className="flex justify-end gap-3 pt-3 border-t border-navy-900 mt-4 select-none">
              <button
                type="button"
                onClick={() => setInspectUserId(null)}
                className="py-2 px-4 bg-navy-900 hover:bg-navy-850 border border-navy-800 rounded-lg text-navy-300 font-bold tracking-wide uppercase transition duration-150 active:scale-95"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
