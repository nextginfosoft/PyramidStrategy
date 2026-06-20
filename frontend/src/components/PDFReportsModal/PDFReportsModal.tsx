import { useState, useEffect } from 'react'
import { tradesApi } from '../../services/api'
import { useToastStore } from '../../store/toastStore'

type PDFReportFile = {
  filename: string
  type: string
  date: string
  size_bytes: number
  created_at: string
}

export function PDFReportsModal({ onClose }: { onClose: () => void }) {
  const addToast = useToastStore(state => state.addToast)
  const [reports, setReports] = useState<PDFReportFile[]>([])
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [triggerDate, setTriggerDate] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState<string | null>(null)

  const fetchReports = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await tradesApi.getReports()
      setReports(data.reports)
    } catch (err: any) {
      console.error(err)
      setError('Failed to fetch PDF reports.')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async (filename: string) => {
    try {
      const blob = await tradesApi.downloadReport(filename)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.parentNode?.removeChild(link)
      window.URL.revokeObjectURL(url)
      addToast('PDF report downloaded successfully.', 'success')
    } catch (err) {
      console.error(err)
      addToast('Failed to download PDF report.', 'error')
    }
  }

  const handleTriggerReport = async () => {
    setTriggering(true)
    try {
      await tradesApi.triggerReport(triggerDate)
      addToast('PDF EOD report generation triggered successfully.', 'success')
      // Refresh after a short delay
      setTimeout(fetchReports, 1500)
    } catch (err: any) {
      console.error(err)
      const detail = err.response?.data?.detail || 'Failed to trigger report generation.'
      addToast(detail, 'error')
    } finally {
      setTriggering(false)
    }
  }

  useEffect(() => {
    fetchReports()
  }, [])

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-navy-950 border border-navy-700 rounded-xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/50">
          <div className="flex items-center gap-2">
            <span className="text-teal-400 text-lg">📋</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">PDF Performance Reports</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-navy-300 hover:text-white transition-colors p-1.5 hover:bg-navy-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Trigger manual report */}
        <div className="p-4 border-b border-navy-700 bg-navy-900/10 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-xs font-bold text-teal-400 uppercase">Trigger Historical Report</h3>
            <p className="text-[11px] text-navy-300">Generate a custom EOD report PDF for testing or backfilled records.</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="date"
              className="bg-navy-900 border border-navy-700 focus:border-teal-500 rounded px-3 py-1.5 text-xs text-white"
              value={triggerDate}
              onChange={e => setTriggerDate(e.target.value)}
            />
            <button
              onClick={handleTriggerReport}
              disabled={triggering}
              className="px-4 py-1.5 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:opacity-40 rounded text-xs font-bold text-white transition-all shadow-md flex items-center gap-1.5"
            >
              {triggering && <span className="w-2.5 h-2.5 border border-white border-t-transparent rounded-full animate-spin" />}
              Generate PDF
            </button>
          </div>
        </div>

        {/* Reports list */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-navy-950/40">
          {error && <div className="text-red-400 text-center py-4 text-xs font-semibold">{error}</div>}
          {loading && reports.length === 0 && (
            <div className="text-navy-300 text-center py-12 text-xs">Loading report archive...</div>
          )}
          {!loading && reports.length === 0 && !error && (
            <div className="text-navy-300 text-center py-12 text-xs">No PDF reports generated yet. Reports are automatically compiled at 12:30 PM.</div>
          )}

          {reports.length > 0 && (
            <div className="overflow-hidden border border-navy-700 rounded-lg">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-navy-900 text-[10px] font-bold text-navy-300 uppercase tracking-wider border-b border-navy-700">
                    <th className="p-3">Report Date</th>
                    <th className="p-3">Report Type</th>
                    <th className="p-3">File Size</th>
                    <th className="p-3">Created At</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800 text-xs text-navy-200">
                  {reports.map((report) => (
                    <tr key={report.filename} className="hover:bg-navy-900/30 transition-colors">
                      <td className="p-3 font-semibold text-white">{new Date(report.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                      <td className="p-3">
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          report.type === 'daily'
                            ? 'bg-blue-900/30 border border-blue-800 text-blue-400'
                            : 'bg-purple-900/30 border border-purple-800 text-purple-400'
                        }`}>
                          {report.type === 'daily' ? 'Daily EOD' : 'Weekly Summary'}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[11px] text-navy-300">{(report.size_bytes / 1024).toFixed(1)} KB</td>
                      <td className="p-3 text-navy-300 font-mono text-[10px]">
                        {new Date(report.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleDownload(report.filename)}
                          className="px-3 py-1 bg-navy-800 hover:bg-navy-700 hover:text-white rounded border border-navy-700 text-[11px] font-semibold transition text-navy-200"
                        >
                          📥 Download PDF
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-navy-700 bg-navy-900/50 flex items-center justify-between text-[10px] text-navy-300 px-5">
          <span>Daily reports generate at 12:30 PM. Weekly briefings on Monday at 9:00 AM.</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-navy-800 hover:bg-navy-700 text-white rounded font-bold text-xs border border-navy-700 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
