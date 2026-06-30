import { useState, useEffect } from 'react'
import { adminApi } from '../../services/api'
import { useToastStore } from '../../store/toastStore'

interface User {
  id: number
  username: string
  is_approved: boolean
  is_admin: boolean
  created_at?: string
}

interface Props {
  onClose: () => void
}

export function AdminPanel({ onClose }: Props) {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [actionId, setActionId] = useState<number | null>(null)
  const addToast = useToastStore(state => state.addToast)

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const data = await adminApi.getUsers()
      setUsers(data)
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to load users'
      addToast(errorMsg, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

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
      const errorMsg = err.response?.data?.detail || err.message || 'Action failed'
      addToast(errorMsg, 'error')
    } finally {
      setActionId(null)
    }
  }

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
      const errorMsg = err.response?.data?.detail || err.message || 'Action failed'
      addToast(errorMsg, 'error')
    } finally {
      setActionId(null)
    }
  }

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
      const errorMsg = err.response?.data?.detail || err.message || 'Deletion failed'
      addToast(errorMsg, 'error')
    } finally {
      setActionId(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-4xl bg-navy-950/90 border border-navy-500/20 rounded-2xl p-6 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Glowing background highlights */}
        <div className="absolute -top-32 -left-32 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-32 -right-32 w-64 h-64 bg-rose-500/10 rounded-full blur-3xl" />

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-navy-800 pb-4 mb-6 z-10">
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="text-xl">🛡️</span>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide">Administrator Controls</h2>
              <p className="text-xs text-navy-300">Moderate signup registrations and assign system authorization policies.</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 bg-navy-900 hover:bg-navy-850 rounded-lg text-navy-300 hover:text-white transition active:scale-95"
            title="Close admin panel"
          >
            ✕
          </button>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto min-h-0 z-10 pr-1">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-navy-300 font-medium">Fetching registered users...</p>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-20 text-navy-400">
              <span className="text-3xl block mb-2">👥</span>
              No users found.
            </div>
          ) : (
            <div className="overflow-x-auto border border-navy-800/80 rounded-xl bg-navy-900/40">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-navy-950/70 border-b border-navy-800 text-[10px] font-bold text-navy-300 uppercase tracking-widest">
                    <th className="py-3 px-4">User ID</th>
                    <th className="py-3 px-4">Username</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-center">Role</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-850 text-xs text-gray-200">
                  {users.map(user => {
                    const isBusy = actionId === user.id
                    return (
                      <tr key={user.id} className="hover:bg-navy-850/30 transition">
                        <td className="py-3 px-4 font-mono text-navy-300">#{user.id}</td>
                        <td className="py-3 px-4 font-semibold text-white">{user.username}</td>
                        <td className="py-3 px-4 text-center">
                          {user.is_approved ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium text-[10px] uppercase">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 font-medium text-[10px] uppercase">
                              Pending
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {user.is_admin ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-medium text-[10px] uppercase">
                              👑 Admin
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-navy-800/80 border border-navy-700 text-navy-300 font-medium text-[10px] uppercase">
                              Trader
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              onClick={() => handleApprove(user.id)}
                              disabled={isBusy}
                              className={`py-1 px-3 rounded-lg font-semibold transition active:scale-95 ${
                                user.is_approved 
                                  ? 'bg-amber-950/20 hover:bg-amber-905/30 hover:bg-amber-900/30 text-amber-400 border border-amber-500/20' 
                                  : 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/35'
                              }`}
                            >
                              {user.is_approved ? 'Suspend' : 'Approve'}
                            </button>
                            
                            <button
                              onClick={() => handleToggleAdmin(user.id)}
                              disabled={isBusy}
                              className={`py-1 px-3 rounded-lg font-semibold border transition active:scale-95 ${
                                user.is_admin
                                  ? 'bg-purple-950/20 hover:bg-purple-900/30 text-purple-400 border-purple-500/20'
                                  : 'bg-cyan-500/10 hover:bg-cyan-500/25 text-cyan-400 border-cyan-500/25'
                              }`}
                            >
                              {user.is_admin ? 'Revoke Admin' : 'Make Admin'}
                            </button>

                            <button
                              onClick={() => handleDelete(user.id, user.username)}
                              disabled={isBusy}
                              className="py-1 px-2.5 bg-red-950/25 hover:bg-red-900/30 text-red-400 border border-red-500/20 rounded-lg font-semibold transition active:scale-95"
                              title="Delete user and purge data"
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
          )}
        </div>
      </div>
    </div>
  )
}
