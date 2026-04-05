interface Props {
  narrative: string
  onDismiss: () => void
}

export function RebalanceInsight({ narrative, onDismiss }: Props) {
  if (!narrative) return null

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">
          Rebalance Insight
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-amber-100 text-amber-700">
            AI
          </span>
          <button
            onClick={onDismiss}
            className="text-gray-400 hover:text-gray-600 text-xs"
            title="Dismiss"
          >
            ✕
          </button>
        </div>
      </div>
      <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
        {narrative}
      </p>
    </div>
  )
}
