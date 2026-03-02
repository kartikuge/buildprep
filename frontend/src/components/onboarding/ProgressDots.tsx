const STEPS = ['Welcome', 'Optional', 'Exam Cycle', 'Study Hours', 'Subjects', 'Review']

export function ProgressDots({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-0 py-6">
      {STEPS.map((_, i) => (
        <div key={i} className="flex items-center">
          <div
            className={`w-2.5 h-2.5 rounded-full transition-colors ${
              i <= current ? 'bg-accent' : 'bg-gray-300'
            }`}
          />
          {i < STEPS.length - 1 && (
            <div
              className={`w-8 h-0.5 transition-colors ${
                i < current ? 'bg-accent' : 'bg-gray-300'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  )
}
