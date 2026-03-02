import { format, parseISO, addDays } from 'date-fns'

interface Props {
  weekStart: string
  onPrev: () => void
  onNext: () => void
}

export function WeekNavigation({ weekStart, onPrev, onNext }: Props) {
  const start = parseISO(weekStart)
  const end = addDays(start, 6)

  return (
    <div className="flex items-center justify-between">
      <button
        onClick={onPrev}
        className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition flex items-center gap-1"
      >
        <span aria-hidden>←</span> Prev
      </button>
      <span className="text-sm font-medium text-gray-700">
        {format(start, 'MMM d')} – {format(end, 'MMM d, yyyy')}
      </span>
      <button
        onClick={onNext}
        className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition flex items-center gap-1"
      >
        Next <span aria-hidden>→</span>
      </button>
    </div>
  )
}
