import { TrendingUp, TrendingDown, Calendar, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Tooltip } from './Tooltip'

function ConfidenceBadge({ tier }) {
  const cls = {
    High: 'badge-high',
    Medium: 'badge-medium',
    Low: 'badge-low',
  }[tier] || 'badge-low'
  return <span className={cls}>{tier} Confidence</span>
}

function ProbabilityGauge({ prob }) {
  const pct = Math.round(prob * 100)
  const isBeat = prob >= 0.5
  const color = isBeat
    ? prob >= 0.65 ? '#10b981' : '#6ee7b7'
    : prob <= 0.35 ? '#ef4444' : '#fca5a5'

  // Arc parameters
  const r = 72
  const cx = 100
  const cy = 100
  const startAngle = -200
  const endAngle = 20
  const totalArc = endAngle - startAngle
  const valueAngle = startAngle + totalArc * prob
  const toRad = (d) => (d * Math.PI) / 180
  const arcPath = (a1, a2) => {
    const x1 = cx + r * Math.cos(toRad(a1))
    const y1 = cy + r * Math.sin(toRad(a1))
    const x2 = cx + r * Math.cos(toRad(a2))
    const y2 = cy + r * Math.sin(toRad(a2))
    const large = Math.abs(a2 - a1) > 180 ? 1 : 0
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`
  }

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 160" className="w-48 h-36">
        {/* Track */}
        <path d={arcPath(startAngle, endAngle)} fill="none" stroke="#1f2937" strokeWidth="14" strokeLinecap="round" />
        {/* Fill */}
        <path d={arcPath(startAngle, valueAngle)} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" />
        {/* Needle dot */}
        <circle
          cx={cx + r * Math.cos(toRad(valueAngle))}
          cy={cy + r * Math.sin(toRad(valueAngle))}
          r="7"
          fill={color}
          className="drop-shadow-lg"
        />
        {/* Center text */}
        <text x={cx} y={cy + 14} textAnchor="middle" fill="white" fontSize="30" fontWeight="700" fontFamily="system-ui">
          {pct}%
        </text>
      </svg>
      <div className="text-center -mt-2">
        <div className={`text-sm font-semibold ${isBeat ? 'text-emerald-400' : 'text-red-400'}`}>
          {isBeat ? '▲ LIKELY BEAT' : '▼ LIKELY MISS'}
        </div>
      </div>
    </div>
  )
}

function FeatureRow({ name, value, description }) {
  const fmt = (k, v) => {
    if (k.includes('drift') || k.includes('momentum') || k.includes('growth') || k.includes('alpha')) {
      return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`
    }
    if (k === 'beat_miss_streak') {
      return v > 0 ? `${v} beat streak` : v < 0 ? `${Math.abs(v)} miss streak` : 'No streak'
    }
    if (k === 'recent_surprise_avg') return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
    if (k === 'iv_rank_proxy') return `${v.toFixed(2)}x`
    if (k === 'analyst_score') return v > 0 ? 'Bullish' : v < 0 ? 'Bearish' : 'Neutral'
    return String(v)
  }

  const isPositive = (k, v) => {
    if (k === 'beat_miss_streak') return v > 0
    if (k === 'iv_rank_proxy') return false
    return v > 0
  }

  const pos = isPositive(name, value)
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <Tooltip text={description}>
        <span className="text-sm text-gray-400">{label}</span>
      </Tooltip>
      <span className={`text-sm font-mono font-semibold ${pos ? 'text-emerald-400' : 'text-red-400'}`}>
        {fmt(name, value)}
      </span>
    </div>
  )
}

export function PredictionCard({ data }) {
  const { ticker, company_name, next_earnings_date, beat_probability, confidence_tier, summary, features, feature_descriptions, model_ready } = data

  const earningsLabel = next_earnings_date
    ? new Date(next_earnings_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : 'Date TBD'

  return (
    <div className="card">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-2xl font-bold text-white">{ticker}</h2>
            <ConfidenceBadge tier={confidence_tier} />
          </div>
          <p className="text-gray-400 text-sm">{company_name}</p>
        </div>
        {next_earnings_date && (
          <div className="flex items-center gap-2 text-sm text-gray-400 bg-gray-800 rounded-lg px-3 py-2">
            <Calendar size={14} className="text-brand-500" />
            Next earnings: <span className="text-white font-medium">{earningsLabel}</span>
          </div>
        )}
      </div>

      {/* Gauge + Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex flex-col items-center justify-center">
          <ProbabilityGauge prob={beat_probability} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Signal Inputs</h3>
          {Object.entries(features).slice(0, 8).map(([k, v]) => (
            <FeatureRow
              key={k}
              name={k}
              value={v}
              description={feature_descriptions?.[k] || k}
            />
          ))}
        </div>
      </div>

      {/* Summary */}
      <div className="mt-6 p-4 bg-gray-800/60 rounded-xl border border-gray-700">
        <div className="flex items-start gap-3">
          {beat_probability >= 0.5
            ? <TrendingUp size={18} className="text-emerald-400 mt-0.5 shrink-0" />
            : <TrendingDown size={18} className="text-red-400 mt-0.5 shrink-0" />
          }
          <p className="text-sm text-gray-200 leading-relaxed">{summary}</p>
        </div>
      </div>

      {data?.data_warning && (
        <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-xs text-yellow-300 flex items-start gap-2">
          <AlertCircle size={13} className="shrink-0 mt-0.5" />
          {data.data_warning}
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-4 flex items-start gap-2 text-xs text-gray-500">
        <AlertCircle size={13} className="shrink-0 mt-0.5" />
        <span>Not financial advice. Predictions are probabilistic estimates based on historical patterns. Past model accuracy is not a guarantee of future results.</span>
      </div>

      {!model_ready && (
        <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-xs text-yellow-300">
          Model not trained yet. Run <code className="font-mono bg-yellow-900/40 px-1 rounded">python train.py</code> in the backend directory to enable predictions.
        </div>
      )}
    </div>
  )
}
