import { format, parseISO } from 'date-fns'
import type { DailyPlan } from '../../types'
import { PlanCardItem } from './PlanCardItem'

interface Props {
  day: DailyPlan
}

export function DayDetail({ day }: Props) {
  const dateObj = parseISO(day.date)

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          {format(dateObj, 'EEEE, MMMM d')}
        </h3>
        {day.finalized ? (
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-green-100 text-green-700">
            Completed
          </span>
        ) : (
          <button
            disabled
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-400 cursor-not-allowed"
          >
            Mark Complete
          </button>
        )}
      </div>

      {day.cards.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">
          Rest day — no tasks scheduled.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {day.cards.map((card) => (
            <PlanCardItem key={card.card_id} card={card} />
          ))}
        </div>
      )}
    </div>
  )
}
