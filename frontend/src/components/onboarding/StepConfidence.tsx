import { SUBJECT_INFO, MAINS_SUBJECTS } from '../../lib/constants'
import type { Subject } from '../../types'

interface Props {
  confidences: Record<string, number>
  optionalSubject: string | null
  onConfidenceChange: (subject: string, value: number) => void
  onNext: () => void
  onBack: () => void
}

const LEVELS = [1, 2, 3, 4, 5]

function levelColor(level: number, selected: number): string {
  if (level > selected) return 'bg-white border-gray-200 text-gray-400'
  if (selected <= 2) return 'bg-red-100 border-red-200 text-red-700'
  if (selected <= 3) return 'bg-amber-100 border-amber-200 text-amber-700'
  return 'bg-green-100 border-green-200 text-green-700'
}

export function StepConfidence({
  confidences,
  optionalSubject,
  onConfidenceChange,
  onNext,
  onBack,
}: Props) {
  const subjects: { key: string; label: string; paper: string }[] = MAINS_SUBJECTS.map(
    (subj: Subject) => ({
      key: subj,
      label: SUBJECT_INFO[subj].label,
      paper: SUBJECT_INFO[subj].paper,
    }),
  )

  if (optionalSubject) {
    subjects.push({
      key: 'OPTIONAL',
      label: optionalSubject,
      paper: 'Optional',
    })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Subject confidence
        </h1>
        <p className="text-lg text-gray-500">
          Rate your comfort level in each subject. Be honest — this shapes your plan.
        </p>
      </div>

      <div className="space-y-3">
        {subjects.map((subj) => {
          const current = confidences[subj.key] ?? 3
          return (
            <div
              key={subj.key}
              className="flex items-center justify-between p-4 rounded-xl border border-gray-200 bg-white"
            >
              <div>
                <div className="font-medium text-gray-900">{subj.label}</div>
                <div className="text-sm text-gray-400">{subj.paper}</div>
              </div>
              <div className="flex gap-1.5">
                {LEVELS.map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => onConfidenceChange(subj.key, lvl)}
                    className={`w-9 h-9 rounded-lg border text-sm font-medium transition ${levelColor(lvl, current)} ${
                      lvl === current ? 'ring-2 ring-offset-1 ring-gray-900/20' : ''
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-red-300" /> Weak
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-300" /> Average
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-green-300" /> Strong
        </span>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-3.5 rounded-xl border border-gray-200 text-gray-700 font-medium hover:bg-gray-50 transition flex items-center gap-2"
        >
          <span aria-hidden>←</span> Back
        </button>
        <button
          onClick={onNext}
          className="flex-1 py-3.5 rounded-xl bg-gray-900 text-white font-medium hover:bg-black transition flex items-center justify-center gap-2"
        >
          Continue <span aria-hidden>→</span>
        </button>
      </div>
    </div>
  )
}
