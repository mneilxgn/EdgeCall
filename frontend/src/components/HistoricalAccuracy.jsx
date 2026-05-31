import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'

function AccuracyBadge({ accuracy, n }) {
  const pct = Math.round(accuracy * 100)
  const color = pct >= 65 ? 'text-emerald-400' : pct >= 55 ? 'text-yellow-400' : 'text-red-400'
  return (
    <div className="text-center">
      <div className={`text-4xl font-bold ${color}`}>{pct}%</div>
      <div className="text-xs text-gray-500 mt-1">accuracy over {n} predictions</div>
    </div>
  )
}

export function HistoricalAccuracy({ data, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center gap-3 py-10 text-gray-400">
        <Loader2 size={18} className="animate-spin" /> Loading historical accuracy…
      </div>
    )
  }

  if (!data || data.n_predictions === 0) {
    return (
      <div className="card text-center py-8 text-gray-500 text-sm">
        No historical predictions available for this ticker.
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-white">Historical Accuracy</h2>
          <p className="text-xs text-gray-500">How EdgeCall performed on past earnings for {data.ticker}</p>
        </div>
        <AccuracyBadge accuracy={data.overall_accuracy} n={data.n_predictions} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-800">
              <th className="text-left pb-2 font-medium">Date</th>
              <th className="text-right pb-2 font-medium">Beat Prob.</th>
              <th className="text-right pb-2 font-medium">Predicted</th>
              <th className="text-right pb-2 font-medium">Actual</th>
              <th className="text-right pb-2 font-medium">Surprise</th>
              <th className="text-right pb-2 font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {data.events.map((e) => (
              <tr key={e.date} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="py-2.5 text-gray-300 font-mono text-xs">{e.date}</td>
                <td className="py-2.5 text-right font-mono">{Math.round(e.beat_probability * 100)}%</td>
                <td className="py-2.5 text-right">
                  <span className={e.predicted_beat ? 'text-emerald-400' : 'text-red-400'}>
                    {e.predicted_beat ? 'Beat' : 'Miss'}
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  <span className={e.actual_beat ? 'text-emerald-400' : 'text-red-400'}>
                    {e.actual_beat ? 'Beat' : 'Miss'}
                  </span>
                </td>
                <td className="py-2.5 text-right font-mono">
                  <span className={e.surprise_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {e.surprise_pct >= 0 ? '+' : ''}{e.surprise_pct?.toFixed(1)}%
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  {e.is_correct
                    ? <CheckCircle2 size={16} className="text-emerald-400 inline" />
                    : <XCircle size={16} className="text-red-400 inline" />
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
