import { useState } from 'react'
import { CATEGORY_COLORS, BLOCK_TYPE_LABELS, SUBJECT_INFO } from '../../lib/constants'
import type { PlanCard, BlockCategory, Subject, CheckInStatus } from '../../types'

interface Props {
  card: PlanCard
  onCheckIn?: (cardId: string, status: 'DONE' | 'PARTIAL' | 'SKIPPED', actualDuration?: number) => void
  isFinalized?: boolean
}

const STATUS_STYLES: Record<string, string> = {
  DONE: 'border-l-4 border-l-green-500',
  PARTIAL: 'border-l-4 border-l-amber-500',
  SKIPPED: 'border-l-4 border-l-gray-300 opacity-60',
}

const STATUS_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  DONE: { bg: 'bg-green-100', text: 'text-green-700', label: 'Done' },
  PARTIAL: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Partial' },
  SKIPPED: { bg: 'bg-gray-100', text: 'text-gray-500', label: 'Skipped' },
}

export function PlanCardItem({ card, onCheckIn, isFinalized }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [partialDuration, setPartialDuration] = useState(
    Math.round(card.planned_duration / 2 / 5) * 5,
  )

  const colors = CATEGORY_COLORS[card.category as BlockCategory] ?? CATEGORY_COLORS.META
  const subjectInfo = card.subject ? SUBJECT_INFO[card.subject as Subject] : null
  const blockLabel = BLOCK_TYPE_LABELS[card.block_type] ?? card.block_type
  const status = card.status as CheckInStatus
  const isCheckedIn = status !== 'PENDING'
  const canInteract = !isCheckedIn && !isFinalized && !!onCheckIn

  const statusStyle = STATUS_STYLES[status] ?? ''
  const badge = STATUS_BADGES[status]

  const handleSelect = (selected: 'DONE' | 'PARTIAL' | 'SKIPPED') => {
    if (selected === 'PARTIAL') {
      setExpanded(true)
      return
    }
    onCheckIn?.(card.card_id, selected)
    setExpanded(false)
  }

  const confirmPartial = () => {
    onCheckIn?.(card.card_id, 'PARTIAL', partialDuration)
    setExpanded(false)
  }

  return (
    <div
      className={`rounded-xl border border-gray-100 bg-gray-50 p-4 space-y-2.5 transition-all ${statusStyle}`}
    >
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
        <div className="flex items-center gap-2">
          {badge && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge.bg} ${badge.text}`}>
              {badge.label}
            </span>
          )}
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full ${colors.bg} ${colors.text}`}
          >
            {card.actual_duration != null ? `${card.actual_duration}/${card.planned_duration}m` : `${card.planned_duration}m`}
          </span>
        </div>
      </div>

      {card.topic && (
        <p className="text-sm text-gray-600 leading-snug">{card.topic}</p>
      )}

      <div className="text-xs text-gray-400">{blockLabel}</div>

      {/* Check-in controls */}
      {canInteract && !expanded && (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => handleSelect('DONE')}
            className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-green-50 text-green-700 hover:bg-green-100 transition"
          >
            Done
          </button>
          <button
            onClick={() => handleSelect('PARTIAL')}
            className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 transition"
          >
            Partial
          </button>
          <button
            onClick={() => handleSelect('SKIPPED')}
            className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition"
          >
            Skip
          </button>
        </div>
      )}

      {/* Partial duration slider */}
      {expanded && (
        <div className="pt-1 space-y-2">
          <label className="text-xs text-gray-500">
            Time spent: <span className="font-semibold text-gray-700">{partialDuration}m</span> / {card.planned_duration}m
          </label>
          <input
            type="range"
            min={0}
            max={card.planned_duration}
            step={5}
            value={partialDuration}
            onChange={(e) => setPartialDuration(Number(e.target.value))}
            className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-amber-500"
          />
          <div className="flex gap-2">
            <button
              onClick={confirmPartial}
              className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition"
            >
              Confirm
            </button>
            <button
              onClick={() => setExpanded(false)}
              className="text-xs text-gray-400 hover:text-gray-600 px-3 transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
