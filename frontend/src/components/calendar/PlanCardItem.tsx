import { CATEGORY_COLORS, BLOCK_TYPE_LABELS, SUBJECT_INFO } from '../../lib/constants'
import type { PlanCard, BlockCategory, Subject } from '../../types'

export function PlanCardItem({ card }: { card: PlanCard }) {
  const colors = CATEGORY_COLORS[card.category as BlockCategory] ?? CATEGORY_COLORS.META
  const subjectInfo = card.subject ? SUBJECT_INFO[card.subject as Subject] : null
  const blockLabel = BLOCK_TYPE_LABELS[card.block_type] ?? card.block_type

  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {subjectInfo && (
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-gray-900">
                {subjectInfo.label}
              </span>
              <span className="text-xs text-gray-400">{subjectInfo.paper}</span>
            </div>
          )}
        </div>
        <span
          className={`text-xs font-semibold px-2.5 py-1 rounded-full ${colors.bg} ${colors.text}`}
        >
          {card.planned_duration}m
        </span>
      </div>

      {card.topic && (
        <p className="text-sm text-gray-600 leading-snug">{card.topic}</p>
      )}

      <div className="text-xs text-gray-400">{blockLabel}</div>
    </div>
  )
}
