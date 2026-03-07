import { format, parseISO, isToday } from 'date-fns'
import type { DailyPlan } from '../../types'
import { SUBJECT_INFO } from '../../lib/constants'
import type { Subject } from '../../types'

interface Props {
  days: DailyPlan[]
  selectedDay: string | null
  onSelectDay: (date: string) => void
}

export function WeekOverview({ days, selectedDay, onSelectDay }: Props) {
  return (
    <div className="grid grid-cols-7 gap-1.5">
      {days.map((day) => {
        const dateObj = parseISO(day.date)
        const isSelected = selectedDay === day.date
        const today = isToday(dateObj)
        const totalMinutes = day.cards.reduce(
          (sum, c) => sum + c.planned_duration,
          0,
        )
        const hours = Math.floor(totalMinutes / 60)
        const mins = totalMinutes % 60

        const subjects = day.cards
          .map((c) =>
            c.subject
              ? SUBJECT_INFO[c.subject as Subject]?.label ?? c.subject
              : null,
          )
          .filter((s): s is string => s !== null)
        const unique = [...new Set(subjects)]
        const shown = unique.slice(0, 2)
        const extra = unique.length - shown.length

        return (
          <button
            key={day.date}
            onClick={() => onSelectDay(day.date)}
            className={`rounded-lg border p-2 text-left transition ${
              isSelected
                ? 'border-accent bg-accent-light shadow-sm'
                : day.finalized
                  ? 'border-green-300 bg-green-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
            } ${today && !isSelected ? 'ring-1 ring-accent/40' : ''}`}
          >
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[10px] font-semibold text-gray-900 uppercase">
                {format(dateObj, 'EEE')}
              </span>
              {day.finalized && (
                <span className="text-green-600 text-[10px]">✓</span>
              )}
            </div>
            <div className="text-base font-bold text-gray-900 mb-1">
              {format(dateObj, 'd')}
            </div>
            <div className="space-y-0.5 mb-1">
              {shown.map((s) => (
                <div
                  key={s}
                  className="text-[10px] text-gray-500 truncate leading-tight"
                >
                  · {s}
                </div>
              ))}
              {extra > 0 && (
                <div className="text-[10px] text-gray-400">+{extra} more</div>
              )}
              {unique.length === 0 && (
                <div className="text-[10px] text-gray-300 italic">Rest</div>
              )}
            </div>
            <div className="text-[10px] font-medium text-gray-400">
              {hours}h{mins > 0 ? `${mins}m` : ''}
            </div>
          </button>
        )
      })}
    </div>
  )
}
