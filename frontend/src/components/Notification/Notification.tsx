import clsx from 'clsx'
import React from 'react'

interface NotificationProps {
  type: 'success' | 'error' | 'warning' | 'info'
  message: React.ReactNode
  onClose?: () => void
  className?: string
  pulse?: boolean
}

export function Notification({ type, message, onClose, className, pulse }: NotificationProps) {
  const styles = {
    success: 'bg-green-950/30 border-green-800/50 text-green-300 shadow-green-950/10',
    error: 'bg-red-950/30 border-red-800/50 text-red-300 shadow-red-950/10',
    warning: 'bg-yellow-950/30 border-yellow-800/50 text-yellow-300 shadow-yellow-950/10',
    info: 'bg-navy-900/30 border-navy-700/50 text-navy-200 shadow-navy-950/10',
  }

  const icons = {
    success: '✓',
    error: '⚠️',
    warning: '⚡',
    info: 'ℹ️',
  }

  return (
    <div
      className={clsx(
        'px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-between gap-3 border transition-all duration-200',
        styles[type],
        pulse && 'animate-pulse',
        className
      )}
    >
      <div className="flex items-center gap-2 flex-1">
        <span className="text-sm font-bold leading-none">{icons[type]}</span>
        <div className="leading-relaxed flex-1">{message}</div>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          type="button"
          className="text-[10px] opacity-60 hover:opacity-100 transition-opacity ml-2 p-0.5 leading-none focus:outline-none focus:ring-1 focus:ring-navy-600 rounded"
        >
          ✕
        </button>
      )}
    </div>
  )
}
