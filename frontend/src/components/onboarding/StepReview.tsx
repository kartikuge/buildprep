import { EXAM_CYCLES } from '../../lib/constants'

const TIME_LABELS: Record<string, string> = {
  morning: 'Morning',
  afternoon: 'Afternoon',
  evening: 'Evening',
  night: 'Night',
}

interface Props {
  name: string
  selectedCycleId: string | null
  optionalSubject: string | null
  hours: number
  preferredTimes: string[]
  confidences: Record<string, number>
  onBack: () => void
  onSubmit: () => void
  isSubmitting: boolean
}

export function StepReview({
  name,
  selectedCycleId,
  optionalSubject,
  hours,
  preferredTimes,
  confidences,
  onBack,
  onSubmit,
  isSubmitting,
}: Props) {
  const cycle = EXAM_CYCLES.find((c) => c.id === selectedCycleId)
  const weakCount = Object.values(confidences).filter((v) => v <= 2).length
  const strongCount = Object.values(confidences).filter((v) => v >= 4).length
  const timesLabel = preferredTimes.map((t) => TIME_LABELS[t] ?? t).join(', ') || '—'

  const rows = [
    {
      label: 'Exam Cycle',
      value: cycle ? `${cycle.label}` : '—',
    },
    { label: 'Optional Subject', value: optionalSubject ?? 'Not selected' },
    { label: 'Daily Hours', value: `${hours} hours` },
    { label: 'Preferred Times', value: timesLabel },
    {
      label: 'Weak Subjects',
      value: weakCount,
      color: weakCount > 0 ? 'text-amber-600' : undefined,
    },
    {
      label: 'Strong Subjects',
      value: strongCount,
      color: strongCount > 0 ? 'text-green-600' : undefined,
    },
  ]

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Ready, {name}?
        </h1>
        <p className="text-lg text-gray-500">
          Here's a summary. We'll generate your personalized weekly schedule.
        </p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between px-5 py-3.5">
            <span className="text-gray-500">{row.label}</span>
            <span className={`font-medium ${row.color ?? 'text-gray-900'}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>

      {weakCount > 0 && (
        <p className="text-sm text-gray-500">
          We'll prioritize your {weakCount} weaker{' '}
          {weakCount === 1 ? 'subject' : 'subjects'} with extra study blocks
          and revision cycles.
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          disabled={isSubmitting}
          className="px-6 py-3.5 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 disabled:opacity-40 transition flex items-center gap-2"
        >
          <span aria-hidden>←</span> Back
        </button>
        <button
          onClick={onSubmit}
          disabled={isSubmitting}
          className="flex-1 py-3.5 rounded-xl bg-accent text-white font-semibold hover:bg-amber-600 disabled:opacity-60 transition flex items-center justify-center gap-2"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Generating...
            </span>
          ) : (
            <>Generate My Schedule</>
          )}
        </button>
      </div>
    </div>
  )
}
