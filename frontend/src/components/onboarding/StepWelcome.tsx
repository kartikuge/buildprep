interface Props {
  name: string
  onNameChange: (name: string) => void
  onNext: () => void
}

export function StepWelcome({ name, onNameChange, onNext }: Props) {
  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <p className="text-sm font-semibold tracking-widest text-accent uppercase">
          UPSC Prep Guide
        </p>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-gray-900 leading-tight">
          Your path to<br />clearing UPSC.
        </h1>
        <p className="text-lg text-gray-500">
          We'll create a personalized study schedule that adapts to your pace,
          strengths, and the time you have.
        </p>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-900">
          What should we call you?
        </label>
        <input
          type="text"
          placeholder="Your first name"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && name.trim() && onNext()}
          className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
        />
      </div>

      <button
        onClick={onNext}
        disabled={!name.trim()}
        className="w-full py-3.5 rounded-xl bg-gray-800 text-white font-medium hover:bg-gray-900 disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
      >
        Get Started <span aria-hidden>→</span>
      </button>
    </div>
  )
}
