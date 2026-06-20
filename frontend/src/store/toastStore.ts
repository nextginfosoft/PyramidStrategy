import { create } from 'zustand'

export interface Toast {
  id: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration: number
}

interface ToastStore {
  toasts: Toast[]
  addToast: (message: string, type?: 'success' | 'error' | 'warning' | 'info', duration?: number) => void
  dismissToast: (id: string) => void
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (message, type = 'info', duration = 4000) => {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast: Toast = { id, message, type, duration }
    
    set((state) => ({ toasts: [...state.toasts, newToast] }))

    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }))
      }, duration)
    }
  },
  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}))
