import { useState } from 'react'
import { Info } from 'lucide-react'

export function Tooltip({ text, children }) {
  const [show, setShow] = useState(false)

  return (
    <span
      className="relative inline-flex items-center gap-1 cursor-pointer group"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      <Info size={13} className="text-gray-500 group-hover:text-gray-300 transition-colors" />
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-64 rounded-lg bg-gray-800 border border-gray-700 text-xs text-gray-200 px-3 py-2 shadow-xl pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-700" />
        </span>
      )}
    </span>
  )
}
