import { SUBJECT_INFO } from '../../lib/constants'
import type { TopicConfidence, Subject } from '../../types'

interface Props {
  confidences: TopicConfidence[]
}

function getTrendArrow(tc: TopicConfidence): string {
  if (tc.streak >= 3) return '↑'
  if (tc.skip_count >= 3) return '↓'
  return '→'
}

function getBarColor(confidence: number): string {
  if (confidence >= 4) return 'bg-green-500'
  if (confidence >= 3) return 'bg-blue-500'
  if (confidence >= 2) return 'bg-amber-500'
  return 'bg-red-500'
}

export function ConfidencePanel({ confidences }: Props) {
  if (confidences.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Subject Confidence
        </h3>
        <p className="text-xs text-gray-400 text-center py-4">
          Complete your first check-in to see confidence scores
        </p>
      </div>
    )
  }

  const sorted = [...confidences].sort(
    (a, b) => a.perceived_confidence - b.perceived_confidence,
  )

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">
        Subject Confidence
      </h3>
      <div className="space-y-3">
        {sorted.map((tc) => {
          const info = SUBJECT_INFO[tc.subject as Subject]
          const label = info?.label ?? tc.subject
          const trend = getTrendArrow(tc)
          const pct = ((tc.perceived_confidence - 1) / 4) * 100

          return (
            <div key={tc.subject}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-700 truncate">
                  {label}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500">
                    {tc.perceived_confidence.toFixed(1)}
                  </span>
                  <span className="text-xs text-gray-400" title={`Streak: ${tc.streak}`}>
                    {trend}
                  </span>
                  {tc.streak > 0 && (
                    <span className="text-[10px] text-green-600 font-medium">
                      {tc.streak}d
                    </span>
                  )}
                </div>
              </div>
              <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${getBarColor(tc.perceived_confidence)}`}
                  style={{ width: `${Math.max(pct, 2)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
