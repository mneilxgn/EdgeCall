import { useState } from 'react'
import { Search, Loader2 } from 'lucide-react'

const QUICK_PICKS = ['AAPL', 'NVDA', 'MSFT', 'META', 'GOOGL', 'AMZN', 'TSLA', 'JPM']

export function SearchBar({ onSearch, loading }) {
  const [value, setValue] = useState('')

  const submit = (ticker) => {
    const t = (ticker || value).trim().toUpperCase()
    if (t) onSearch(t)
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form
        onSubmit={(e) => { e.preventDefault(); submit() }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            placeholder="Enter ticker symbol (e.g. NVDA)"
            className="w-full bg-gray-900 border border-gray-700 rounded-xl pl-11 pr-4 py-3.5 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-colors text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-6 py-3.5 rounded-xl transition-colors flex items-center gap-2 text-sm whitespace-nowrap"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : null}
          {loading ? 'Loading…' : 'Predict'}
        </button>
      </form>

      {/* Quick picks */}
      <div className="flex flex-wrap gap-2 mt-3 justify-center">
        <span className="text-xs text-gray-500 self-center">Quick:</span>
        {QUICK_PICKS.map((t) => (
          <button
            key={t}
            onClick={() => { setValue(t); submit(t) }}
            className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors font-mono"
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  )
}
