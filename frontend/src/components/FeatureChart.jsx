import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const COLORS = [
  '#4f6ef7', '#6366f1', '#8b5cf6', '#a855f7',
  '#c084fc', '#d946ef', '#ec4899', '#f43f5e',
  '#fb7185', '#fda4af', '#fecdd3',
]

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 max-w-xs text-xs shadow-xl">
      <p className="font-semibold text-white mb-1">{d.feature.replace(/_/g, ' ')}</p>
      <p className="text-brand-400 mb-1.5">{d.importance}% of model weight</p>
      <p className="text-gray-400 leading-relaxed">{d.description}</p>
    </div>
  )
}

export function FeatureChart({ features }) {
  const data = [...features].sort((a, b) => a.importance - b.importance)

  return (
    <div className="card">
      <h2 className="text-lg font-bold text-white mb-1">Feature Importance</h2>
      <p className="text-xs text-gray-500 mb-5">What drives the model's predictions (hover for details)</p>
      <div style={{ height: Math.max(280, data.length * 38) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48, top: 4, bottom: 4 }}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="feature"
              width={190}
              tick={{ fill: '#9ca3af', fontSize: 12 }}
              tickFormatter={(v) =>
                v.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
              }
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey="importance" radius={[0, 6, 6, 0]} label={{ position: 'right', fill: '#6b7280', fontSize: 11, formatter: (v) => `${v}%` }}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
