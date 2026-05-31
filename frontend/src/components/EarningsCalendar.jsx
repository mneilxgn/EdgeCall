import { Calendar, Loader2, TrendingUp, TrendingDown } from 'lucide-react'

function ConfidenceDot({ tier }) {
  const map = { High: 'bg-emerald-400', Medium: 'bg-yellow-400', Low: 'bg-gray-500' }
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${map[tier] || 'bg-gray-500'} mr-1.5`} />
  )
}

function ProbBar({ prob }) {
  const pct = Math.round(prob * 100)
  const isBeat = prob >= 0.5
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-800 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${isBeat ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-semibold w-9 text-right ${isBeat ? 'text-emerald-400' : 'text-red-400'}`}>
        {pct}%
      </span>
    </div>
  )
}

export function EarningsCalendar({ data, loading, onSelectTicker }) {
  const formatDate = (iso) => {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-5">
        <Calendar size={18} className="text-brand-500" />
        <div>
          <h2 className="text-lg font-bold text-white leading-tight">Earnings Calendar</h2>
          <p className="text-xs text-gray-500">Large-cap earnings in the next 2 weeks</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-3 py-10 text-gray-400">
          <Loader2 size={18} className="animate-spin" /> Loading calendar…
        </div>
      ) : !data?.calendar?.length ? (
        <div className="text-center py-8 text-gray-500 text-sm">
          No upcoming large-cap earnings found in the next 14 days, or the model isn't trained yet.
        </div>
      ) : (
        <div className="space-y-2">
          {data.calendar.map((item) => (
            <button
              key={item.ticker}
              onClick={() => onSelectTicker(item.ticker)}
              className="w-full flex items-center gap-3 p-3 rounded-xl bg-gray-800/50 hover:bg-gray-800 border border-transparent hover:border-gray-700 transition-all text-left group"
            >
              <div className="min-w-[52px]">
                <span className="font-bold text-white font-mono text-sm group-hover:text-brand-400 transition-colors">
                  {item.ticker}
                </span>
              </div>

              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-400 truncate mb-1">{item.company_name}</div>
                <ProbBar prob={item.beat_probability} />
              </div>

              <div className="flex flex-col items-end gap-1 shrink-0">
                <span className="text-xs text-gray-500">{formatDate(item.earnings_date)}</span>
                <div className="flex items-center text-xs">
                  <ConfidenceDot tier={item.confidence_tier} />
                  <span className="text-gray-400">{item.confidence_tier}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
