import { useToastStore, Toast as ToastType } from '../../store/toastStore'
import clsx from 'clsx'

function ToastItem({ toast }: { toast: ToastType }) {
  const dismissToast = useToastStore((state) => state.dismissToast)

  const styles = {
    success: 'bg-emerald-950/90 border-emerald-800 text-emerald-300 shadow-emerald-950/20',
    error: 'bg-red-950/90 border-red-800 text-red-300 shadow-red-950/20',
    warning: 'bg-amber-950/90 border-amber-800 text-amber-300 shadow-amber-950/20',
    info: 'bg-navy-900/90 border-navy-700 text-navy-200 shadow-navy-950/20',
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
        'flex items-start gap-3 p-3.5 rounded-xl border backdrop-blur-xl shadow-lg transition-all duration-350 w-80 font-mono text-xs animate-slide-in-right border-l-4',
        styles[toast.type]
      )}
      style={{
        borderLeftColor: toast.type === 'success' ? '#10b981' : toast.type === 'error' ? '#ef4444' : toast.type === 'warning' ? '#f59e0b' : '#3b82f6'
      }}
    >
      <span className="text-sm font-bold leading-none mt-0.5">{icons[toast.type]}</span>
      <div className="flex-1 text-[11px] leading-relaxed">{toast.message}</div>
      <button
        onClick={() => dismissToast(toast.id)}
        className="text-[10px] text-navy-300 hover:text-white transition-colors ml-1 p-0.5 leading-none focus:outline-none"
      >
        ✕
      </button>
    </div>
  )
}

export function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts)

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2.5 pointer-events-none">
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} />
        </div>
      ))}
    </div>
  )
}
