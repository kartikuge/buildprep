import { useState } from 'react'
import { OPTIONAL_SUBJECTS } from '../../lib/constants'

interface Props {
  optionalSubject: string | null
  onSubjectChange: (subject: string | null) => void
  onNext: () => void
  onBack: () => void
}

export function StepOptionalSubject({
  optionalSubject,
  onSubjectChange,
  onNext,
  onBack,
}: Props) {
  const [filter, setFilter] = useState('')

  const filtered = filter
    ? OPTIONAL_SUBJECTS.filter((s) =>
        s.toLowerCase().includes(filter.toLowerCase()),
      )
    : OPTIONAL_SUBJECTS

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Optional subject
        </h1>
        <p className="text-lg text-gray-500">
          Pick your optional paper, or skip if you haven't decided yet.
        </p>
      </div>

      <button
        onClick={() => {
          onSubjectChange(null)
          onNext()
        }}
        className="w-full p-4 rounded-xl border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition text-left"
      >
        Skip — I haven't decided yet
      </button>

      <input
        type="text"
        placeholder="Search subjects..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-900 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
      />

      <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
        {filtered.map((subject) => (
          <button
            key={subject}
            onClick={() => onSubjectChange(subject)}
            className={`w-full text-left p-3.5 rounded-xl border transition ${
              optionalSubject === subject
                ? 'border-accent bg-accent-light'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <span className="font-medium text-gray-900">{subject}</span>
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-4">
            No subjects match "{filter}"
          </p>
        )}
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
          disabled={!optionalSubject}
          className="flex-1 py-3.5 rounded-xl bg-gray-900 text-white font-medium hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
        >
          Continue <span aria-hidden>→</span>
        </button>
      </div>
    </div>
  )
}
