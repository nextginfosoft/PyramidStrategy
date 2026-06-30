import { useEffect, useRef } from 'react'

interface ChartModalProps {
  onClose: () => void
}

export function ChartModal({ onClose }: ChartModalProps) {
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!container.current) return
    container.current.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: "NSE:NIFTY",
      interval: "5",
      timezone: "Asia/Kolkata",
      theme: "dark",
      style: "1",
      locale: "en",
      enable_publishing: false,
      hide_side_toolbar: false,
      allow_symbol_change: true,
      container_id: "tradingview_nifty_chart"
    })
    container.current.appendChild(script)
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/80 backdrop-blur-sm p-4 animate-fade-in select-none">
      <div className="bg-navy-900 border border-navy-800 rounded-2xl w-full h-full max-w-[1400px] max-h-[85vh] flex flex-col overflow-hidden shadow-2xl shadow-black/80">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-navy-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">📈</span>
            <h3 className="text-sm font-bold tracking-wider text-white uppercase">NIFTY 50 Live Chart</h3>
          </div>
          <button 
            onClick={onClose}
            className="text-navy-400 hover:text-white bg-navy-950/40 hover:bg-navy-800/80 border border-navy-800/60 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-150 focus:outline-none"
          >
            ✕ Close
          </button>
        </div>

        {/* Chart Viewport */}
        <div className="flex-1 w-full bg-navy-950 p-2 relative">
          <div className="tradingview-widget-container w-full h-full">
            <div id="tradingview_nifty_chart" ref={container} className="w-full h-full" style={{ height: "100%", width: "100%" }} />
          </div>
        </div>

      </div>
    </div>
  )
}
