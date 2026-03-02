import { differenceInDays, parseISO, format } from 'date-fns'
import { EXAM_CYCLES, getStudyPhase } from '../../lib/constants'

interface Props {
  selectedCycleId: string | null
  onCycleChange: (cycleId: string) => void
  onNext: () => void
  onBack: () => void
}

export function StepExamDate({ selectedCycleId, onCycleChange, onNext, onBack }: Props) {
  const today = new Date()
  const selectedCycle = EXAM_CYCLES.find((c) => c.id === selectedCycleId)

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Which exam cycle?
        </h1>
        <p className="text-lg text-gray-500">
          Pick your target UPSC CSE cycle. This sets your study phases
          automatically.
        </p>
      </div>

      <div className="space-y-3">
        {EXAM_CYCLES.map((cycle) => {
          const daysToP = differenceInDays(parseISO(cycle.prelimsDate), today)
          if (daysToP < 0) return null
          const phase = getStudyPhase(daysToP)
          const isSelected = selectedCycleId === cycle.id

          return (
            <button
              key={cycle.id}
              onClick={() => onCycleChange(cycle.id)}
              className={`w-full text-left p-4 rounded-xl border transition ${
                isSelected
                  ? 'border-accent bg-accent-light'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-900 text-lg">
                  {cycle.label}
                </span>
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-green-100 text-green-700">
                  {phase}
                </span>
              </div>
              <div className="text-sm text-gray-500 space-y-0.5">
                <div>
                  Prelims: {format(parseISO(cycle.prelimsDate), 'MMM d, yyyy')}
                </div>
                <div>
                  Mains: {format(parseISO(cycle.mainsDate), 'MMM d, yyyy')}
                </div>
              </div>
              <div className="mt-2 text-xs text-gray-400">
                {daysToP} days to Prelims
              </div>
            </button>
          )
        })}
      </div>

      {selectedCycle && (
        <div className="rounded-xl bg-green-50 border border-green-200 p-4">
          <p className="text-sm font-medium text-green-800">
            {differenceInDays(parseISO(selectedCycle.prelimsDate), today)} days
            until Prelims — you're in{' '}
            <span className="font-semibold">
              {getStudyPhase(
                differenceInDays(parseISO(selectedCycle.prelimsDate), today),
              )}
            </span>{' '}
            phase. Let's make every day count.
          </p>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-3.5 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition flex items-center gap-2"
        >
          <span aria-hidden>←</span> Back
        </button>
        <button
          onClick={onNext}
          disabled={!selectedCycleId}
          className="flex-1 py-3.5 rounded-xl bg-gray-800 text-white font-medium hover:bg-gray-900 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
        >
          Continue <span aria-hidden>→</span>
        </button>
      </div>
    </div>
  )
}
