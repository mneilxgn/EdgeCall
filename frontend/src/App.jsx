import { useState, useEffect, useCallback } from 'react'
import { TrendingUp, Zap, AlertCircle, ChevronDown, RotateCcw, Loader2 } from 'lucide-react'
import { SearchBar } from './components/SearchBar'
import { PredictionCard } from './components/PredictionCard'
import { FeatureChart } from './components/FeatureChart'
import { HistoricalAccuracy } from './components/HistoricalAccuracy'
import { EarningsCalendar } from './components/EarningsCalendar'
import { api } from './api'

function ModelStatusBar({ health }) {
  if (!health) return null
  const ready = health.model_ready
  return (
    <div className={`flex items-center justify-center gap-2 py-2 px-4 text-xs ${ready ? 'bg-emerald-900/30 text-emerald-400 border-b border-emerald-800/30' : 'bg-yellow-900/30 text-yellow-400 border-b border-yellow-800/30'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ready ? 'bg-emerald-400' : 'bg-yellow-400'} animate-pulse`} />
      {ready
        ? `Model ready — trained on ${health.model_meta?.n_samples?.toLocaleString() || '?'} earnings events | CV AUC: ${health.model_meta?.cv_auc_mean?.toFixed(3) || '?'}`
        : 'Model not trained. Run python train.py in the backend directory to enable full predictions.'}
    </div>
  )
}

export default function App() {
  const [ticker, setTicker] = useState(null)
  const [prediction, setPrediction] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [featureImportance, setFeatureImportance] = useState(null)
  const [calendar, setCalendar] = useState(null)
  const [health, setHealth] = useState(null)

  const [loadingPredict, setLoadingPredict] = useState(false)
  const [loadingAccuracy, setLoadingAccuracy] = useState(false)
  const [loadingCalendar, setLoadingCalendar] = useState(false)
  const [error, setError] = useState(null)

  const [activeTab, setActiveTab] = useState('prediction')

  // Fetch health + feature importance + calendar on mount
  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
    api.featureImportance().then(setFeatureImportance).catch(() => {})
    setLoadingCalendar(true)
    api.calendar().then(setCalendar).catch(() => {}).finally(() => setLoadingCalendar(false))
  }, [])

  const handleSearch = useCallback(async (t) => {
    setTicker(t)
    setError(null)
    setPrediction(null)
    setAccuracy(null)
    setActiveTab('prediction')

    setLoadingPredict(true)
    try {
      const data = await api.predict(t)
      setPrediction(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingPredict(false)
    }

    setLoadingAccuracy(true)
    try {
      const acc = await api.accuracy(t)
      setAccuracy(acc)
    } catch (e) {
      // non-fatal
    } finally {
      setLoadingAccuracy(false)
    }
  }, [])

  const handleCalendarSelect = (t) => {
    handleSearch(t)
    // Scroll to top smoothly
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const tabs = [
    { id: 'prediction', label: 'Prediction' },
    { id: 'accuracy', label: 'Historical Accuracy' },
    { id: 'features', label: 'Feature Importance' },
  ]

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Top nav */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-40">
        <ModelStatusBar health={health} />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
              <Zap size={16} className="text-white" fill="white" />
            </div>
            <span className="text-lg font-bold text-white tracking-tight">EdgeCall</span>
            <span className="hidden sm:inline text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full ml-1">AI Earnings Predictor</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <AlertCircle size={12} />
            <span className="hidden sm:inline">Not financial advice</span>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-12 pb-8">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs px-3 py-1.5 rounded-full mb-4">
            <TrendingUp size={12} />
            Quant-grade earnings signals for retail investors
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
            Will they beat <span className="text-brand-500">earnings?</span>
          </h1>
          <p className="text-gray-400 text-base sm:text-lg max-w-xl mx-auto">
            EdgeCall uses an XGBoost model trained on 5+ years of earnings history to predict whether a company will beat or miss estimates.
          </p>
        </div>

        {/* Search */}
        <SearchBar onSearch={handleSearch} loading={loadingPredict} />
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pb-16">
        {error && (
          <div className="max-w-2xl mx-auto mb-6 p-4 bg-red-900/20 border border-red-800/30 rounded-xl flex items-center gap-3 text-sm text-red-300">
            <AlertCircle size={16} className="shrink-0" />
            {error}
          </div>
        )}

        {loadingPredict && (
          <div className="max-w-2xl mx-auto flex items-center justify-center gap-3 py-16 text-gray-400">
            <Loader2 size={20} className="animate-spin" />
            Fetching data and computing signals for {ticker}…
          </div>
        )}

        {prediction && !loadingPredict && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
            {/* Left: tabs */}
            <div className="xl:col-span-2 space-y-4">
              {/* Tabs */}
              <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 w-fit">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`text-sm px-4 py-2 rounded-lg transition-all ${activeTab === tab.id ? 'bg-brand-500 text-white font-semibold' : 'text-gray-400 hover:text-white'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {activeTab === 'prediction' && <PredictionCard data={prediction} />}
              {activeTab === 'accuracy' && (
                <HistoricalAccuracy data={accuracy} loading={loadingAccuracy} />
              )}
              {activeTab === 'features' && featureImportance && (
                <FeatureChart features={featureImportance.features} />
              )}
            </div>

            {/* Right: calendar */}
            <div className="xl:col-span-1">
              <EarningsCalendar
                data={calendar}
                loading={loadingCalendar}
                onSelectTicker={handleCalendarSelect}
              />
            </div>
          </div>
        )}

        {/* When no search yet: show calendar full width */}
        {!prediction && !loadingPredict && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <EarningsCalendar
              data={calendar}
              loading={loadingCalendar}
              onSelectTicker={handleCalendarSelect}
            />
            {featureImportance && (
              <FeatureChart features={featureImportance.features} />
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 text-center text-xs text-gray-600">
        <p className="mb-1">EdgeCall is for educational purposes only. Not financial advice.</p>
        <p>Data sourced from Yahoo Finance. Model accuracy varies by market conditions.</p>
      </footer>
    </div>
  )
}
