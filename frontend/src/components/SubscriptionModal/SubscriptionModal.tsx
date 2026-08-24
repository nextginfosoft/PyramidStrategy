import React, { useState, useEffect } from 'react'
import { paymentsApi } from '../../services/api'
import { useToastStore } from '../../store/toastStore'

interface Plan {
  id: number
  plan_code: string
  name: string
  description: string
  billing_period: string
  interval_count: number
  price: number
  discount_percentage: number
}

interface Props {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  onLoginRequired?: () => void
}

declare global {
  interface Window {
    Razorpay: any
  }
}

export function SubscriptionModal({ isOpen, onClose, onSuccess, onLoginRequired }: Props) {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(false)
  const [processingCode, setProcessingCode] = useState<string | null>(null)
  const addToast = useToastStore(state => state.addToast)

  useEffect(() => {
    if (isOpen) {
      fetchPlans()
    }
  }, [isOpen])

  const fetchPlans = async () => {
    try {
      setLoading(true)
      const data = await paymentsApi.getPlans()
      setPlans(data)
    } catch (err: any) {
      if (err.response?.status === 401 && onLoginRequired) {
        addToast('Please log in or register to subscribe to Pro plans.', 'info')
        onLoginRequired()
        return
      }
      addToast(err.response?.data?.detail || 'Failed to load subscription plans', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSubscribe = async (plan: Plan) => {
    try {
      setProcessingCode(plan.plan_code)
      const order = await paymentsApi.createOrder(plan.plan_code)

      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'PyramidStrategy Pro',
        description: `Subscription to ${order.plan_name}`,
        order_id: order.order_id,
        handler: async function (response: any) {
          try {
            await paymentsApi.verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              plan_code: plan.plan_code
            })
            addToast(`🎉 Successfully subscribed to ${plan.name}! Live trading enabled.`, 'success')
            if (onSuccess) onSuccess()
            onClose()
          } catch (verifyErr: any) {
            addToast(verifyErr.response?.data?.detail || 'Payment verification failed', 'error')
          }
        },
        theme: {
          color: '#4f46e5'
        }
      }

      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', function (response: any) {
        addToast(`Payment failed: ${response.error.description || 'Transaction declined'}`, 'error')
      })
      rzp.open()
    } catch (err: any) {
      addToast(err.response?.data?.detail || 'Failed to initiate payment', 'error')
    } finally {
      setProcessingCode(null)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl p-6 sm:p-8 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white text-2xl font-bold p-2 rounded-lg transition-colors"
        >
          ✕
        </button>

        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-3">
            ⚡ Upgrade Access
          </div>
          <h2 className="text-3xl font-extrabold text-white">Unlock Live Trading with Pro</h2>
          <p className="text-slate-400 mt-2 text-sm max-w-lg mx-auto">
            Choose a Pro subscription plan below to enable automated Zerodha Kite live order execution with full risk management controls.
          </p>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map(plan => {
              const isQuarterly = plan.plan_code === 'PRO_QUARTERLY'
              const isAnnual = plan.plan_code === 'PRO_ANNUAL'
              const isFeatured = isQuarterly

              return (
                <div
                  key={plan.id}
                  className={`relative flex flex-col justify-between rounded-2xl p-6 transition-all duration-200 ${
                    isFeatured
                      ? 'bg-slate-800/90 border-2 border-indigo-500 shadow-lg shadow-indigo-500/20 scale-[1.02]'
                      : 'bg-slate-950/70 border border-slate-800 hover:border-slate-700'
                  }`}
                >
                  {plan.discount_percentage > 0 && (
                    <div className="absolute -top-3 right-4 bg-emerald-500 text-slate-950 text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                      {plan.discount_percentage}% OFF
                    </div>
                  )}

                  <div>
                    <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                    <p className="text-xs text-slate-400 mt-1 min-h-[32px]">{plan.description}</p>

                    <div className="my-6">
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-extrabold text-white">₹{plan.price.toLocaleString('en-IN')}</span>
                        <span className="text-xs text-slate-400">
                          / {plan.interval_count > 1 ? `${plan.interval_count} mos` : plan.billing_period}
                        </span>
                      </div>
                      {plan.discount_percentage > 0 && (
                        <p className="text-xs text-emerald-400 font-medium mt-1">
                          Effective ~₹{Math.round(plan.price / (plan.interval_count || 1)).toLocaleString('en-IN')}/month
                        </p>
                      )}
                    </div>

                    <ul className="space-y-2.5 mb-6 text-xs text-slate-300">
                      <li className="flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">✓</span> Live Broker Execution (Zerodha)
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">✓</span> Unlimited Paper Trading
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">✓</span> Telegram & SMS Execution Alerts
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="text-emerald-400 font-bold">✓</span> Risk Controls & Auto Square-off
                      </li>
                    </ul>
                  </div>

                  <button
                    onClick={() => handleSubscribe(plan)}
                    disabled={processingCode === plan.plan_code}
                    className={`w-full py-3 rounded-xl text-xs font-bold transition-all shadow-md ${
                      isFeatured
                        ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30'
                        : 'bg-slate-800 hover:bg-slate-700 text-white'
                    } disabled:opacity-50`}
                  >
                    {processingCode === plan.plan_code ? 'Opening Gateway...' : `Subscribe ${plan.name}`}
                  </button>
                </div>
              )
            })}
          </div>
        )}

        <div className="mt-8 text-center border-t border-slate-800/80 pt-4">
          <p className="text-xs text-slate-500">
            🔒 Secure payment processed via Razorpay. UPI, Netbanking, Credit/Debit Cards supported.
          </p>
        </div>
      </div>
    </div>
  )
}
