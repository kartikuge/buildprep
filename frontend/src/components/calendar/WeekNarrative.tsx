import type { DailyPlan } from '../../types'

interface Props {
  narrative: string
  days: DailyPlan[]
  phase: string
}

export function WeekNarrative({ narrative, days, phase }: Props) {
  if (!narrative) return null

  const totalMinutes = days.reduce(
    (sum, day) =>
      sum + day.cards.reduce((s, c) => s + c.planned_duration, 0),
    0,
  )
  const totalHours = Math.round(totalMinutes / 60)

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">
          Schedule Insights
        </h3>
        <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-blue-100 text-blue-700">
          AI
        </span>
      </div>
      <p className="text-sm text-gray-600 mb-2">
        This week: {totalHours}h of study, {phase} phase.
      </p>
      <p className="text-sm text-gray-500 leading-relaxed whitespace-pre-line">
        {narrative}
      </p>
    </div>
  )
}
