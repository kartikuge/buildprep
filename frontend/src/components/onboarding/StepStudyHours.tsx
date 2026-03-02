const TIME_SLOTS = [
  { id: 'morning', label: 'Morning', range: '6am – 12pm', icon: '☀️' },
  { id: 'afternoon', label: 'Afternoon', range: '12pm – 5pm', icon: '🌤' },
  { id: 'evening', label: 'Evening', range: '5pm – 9pm', icon: '🌅' },
  { id: 'night', label: 'Night', range: '9pm – 1am', icon: '🌙' },
] as const

interface Props {
  hours: number
  preferredTimes: string[]
  onHoursChange: (hours: number) => void
  onTimesChange: (times: string[]) => void
  onNext: () => void
  onBack: () => void
}

export function StepStudyHours({
  hours,
  preferredTimes,
  onHoursChange,
  onTimesChange,
  onNext,
  onBack,
}: Props) {
  const toggleTime = (id: string) => {
    if (preferredTimes.includes(id)) {
      onTimesChange(preferredTimes.filter((t) => t !== id))
    } else {
      onTimesChange([...preferredTimes, id])
    }
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Study routine
        </h1>
        <p className="text-lg text-gray-500">
          How many hours can you realistically dedicate daily?
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium text-gray-900">Daily study hours</span>
          <span className="text-3xl font-bold text-gray-900">
            {hours} <span className="text-base font-normal text-gray-500">hrs</span>
          </span>
        </div>
        <input
          type="range"
          min={2}
          max={14}
          step={0.5}
          value={hours}
          onChange={(e) => onHoursChange(parseFloat(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer accent-gray-900"
          style={{
            background: `linear-gradient(to right, #1f2937 0%, #1f2937 ${((hours - 2) / 12) * 100}%, #e5e7eb ${((hours - 2) / 12) * 100}%, #e5e7eb 100%)`,
          }}
        />
        <div className="flex justify-between text-xs text-gray-400">
          <span>2 hrs</span>
          <span>14 hrs</span>
        </div>
      </div>

      <div className="space-y-3">
        <span className="text-sm font-medium text-gray-900">
          Preferred study times{' '}
          <span className="text-gray-400 font-normal">(select all that apply)</span>
        </span>
        <div className="grid grid-cols-2 gap-3">
          {TIME_SLOTS.map((slot) => (
            <button
              key={slot.id}
              onClick={() => toggleTime(slot.id)}
              className={`p-4 rounded-xl border text-left transition ${
                preferredTimes.includes(slot.id)
                  ? 'border-accent bg-accent-light'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="text-lg mb-1">{slot.icon}</div>
              <div className="font-medium text-gray-900">{slot.label}</div>
              <div className="text-sm text-gray-500">{slot.range}</div>
            </button>
          ))}
        </div>
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
          disabled={preferredTimes.length === 0}
          className="flex-1 py-3.5 rounded-xl bg-gray-900 text-white font-medium hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
        >
          Continue <span aria-hidden>→</span>
        </button>
      </div>
    </div>
  )
}
