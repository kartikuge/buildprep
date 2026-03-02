export function LoadingScreen() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center space-y-6">
        <div className="relative w-16 h-16 mx-auto">
          <div className="absolute inset-0 rounded-full border-4 border-gray-200" />
          <div className="absolute inset-0 rounded-full border-4 border-accent border-t-transparent animate-spin" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-gray-900">
            Building your schedule
          </h2>
          <p className="text-gray-500 max-w-xs">
            Our AI is analyzing your profile and creating a personalized study
            plan. This may take 10–30 seconds.
          </p>
        </div>
      </div>
    </div>
  )
}
