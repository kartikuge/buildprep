import { format, parseISO } from 'date-fns'
import type { DailyPlan } from '../../types'
import { PlanCardItem } from './PlanCardItem'

export function DayCard({ day }: { day: DailyPlan }) {
  const dateObj = parseISO(day.date)
  const totalMinutes = day.cards.reduce((sum, c) => sum + c.planned_duration, 0)
  const hours = Math.floor(totalMinutes / 60)
  const mins = totalMinutes % 60

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {format(dateObj, 'EEEE')}
          </div>
          <div className="text-xs text-gray-400">{format(dateObj, 'MMM d')}</div>
        </div>
        <span className="text-xs font-medium text-gray-500 bg-white px-2 py-1 rounded-md border border-gray-100">
          {hours > 0 ? `${hours}h ` : ''}{mins > 0 ? `${mins}m` : hours > 0 ? '' : '0m'}
        </span>
      </div>

      <div className="p-3 space-y-2">
        {day.cards.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">Rest day</p>
        ) : (
          day.cards.map((card) => <PlanCardItem key={card.card_id} card={card} />)
        )}
      </div>
    </div>
  )
}
