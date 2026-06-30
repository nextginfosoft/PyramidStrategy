import { useEffect, useRef } from 'react'

export function EmbeddedChart() {
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
      container_id: "tradingview_embedded_nifty"
    })
    container.current.appendChild(script)
  }, [])

  return (
    <div className="glass-card rounded-xl p-3 flex flex-col h-[400px] border border-navy-800/40 shadow-lg relative overflow-hidden">
      <div className="text-xs text-navy-300 mb-2 font-semibold flex items-center gap-1.5 select-none">
        <span>📈</span> LIVE NIFTY CHART (5M)
      </div>
      <div className="flex-1 w-full bg-navy-950 rounded-lg overflow-hidden relative">
        <div className="tradingview-widget-container w-full h-full">
          <div id="tradingview_embedded_nifty" ref={container} className="w-full h-full" style={{ height: "100%", width: "100%" }} />
        </div>
      </div>
    </div>
  )
}
