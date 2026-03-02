import { useMemo } from 'react'
import { addDays, subDays, format, differenceInWeeks, parseISO } from 'date-fns'
import { usePlan } from '../../hooks/usePlan'
import { useUserStore } from '../../store/userStore'
import { getStudyPhase } from '../../lib/constants'
import { WeekOverview } from './WeekOverview'
import { WeekNarrative } from './WeekNarrative'
import { DayDetail } from './DayDetail'

export function CalendarView() {
  const {
    userId,
    displayName,
    weekStart,
    selectedDay,
    prelimsDate,
    firstWeekStart,
    setWeekStart,
    setSelectedDay,
    logout,
  } = useUserStore()

  const { data: plan, isLoading, error } = usePlan(userId, weekStart)

  const handlePrev = () => {
    if (!weekStart) return
    const prev = subDays(new Date(weekStart + 'T00:00:00'), 7)
    setWeekStart(format(prev, 'yyyy-MM-dd'))
  }

  const handleNext = () => {
    if (!weekStart) return
    const next = addDays(new Date(weekStart + 'T00:00:00'), 7)
    setWeekStart(format(next, 'yyyy-MM-dd'))
  }

  const weekNumber = useMemo(() => {
    if (!weekStart || !firstWeekStart) return 1
    return (
      differenceInWeeks(
        new Date(weekStart + 'T00:00:00'),
        new Date(firstWeekStart + 'T00:00:00'),
      ) + 1
    )
  }, [weekStart, firstWeekStart])

  const phase = useMemo(() => {
    if (!prelimsDate) return 'Foundation'
    const today = new Date()
    const days = Math.max(
      0,
      Math.ceil(
        (parseISO(prelimsDate).getTime() - today.getTime()) /
          (1000 * 60 * 60 * 24),
      ),
    )
    return getStudyPhase(days)
  }, [prelimsDate])

  const daysCompleted = plan
    ? plan.days.filter((d) => d.finalized).length
    : 0

  const effectiveSelectedDay = useMemo(() => {
    if (!plan) return null
    if (
      selectedDay &&
      plan.days.some((d) => d.date === selectedDay)
    )
      return selectedDay
    const today = format(new Date(), 'yyyy-MM-dd')
    if (plan.days.some((d) => d.date === today)) return today
    return plan.days[0]?.date ?? null
  }, [plan, selectedDay])

  const selectedDayPlan = plan?.days.find(
    (d) => d.date === effectiveSelectedDay,
  )

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-1">
            <div>
              <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-0.5 rounded-full uppercase tracking-wider">
                {phase} Phase
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-400">
                Hi, {displayName}
              </span>
              <button
                onClick={logout}
                className="text-xs text-gray-400 hover:text-gray-600 transition"
              >
                Reset
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between mt-2">
            <h1 className="text-xl font-bold text-gray-900">
              Week {weekNumber}
            </h1>
            <span className="text-sm text-gray-500">
              {daysCompleted}/7 days done
            </span>
          </div>
          <div className="flex items-center justify-center gap-4 mt-3">
            <button
              onClick={handlePrev}
              className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              ← Prev
            </button>
            {weekStart && (
              <span className="text-sm font-medium text-gray-700">
                {format(
                  new Date(weekStart + 'T00:00:00'),
                  'MMM d',
                )}{' '}
                –{' '}
                {format(
                  addDays(new Date(weekStart + 'T00:00:00'), 6),
                  'MMM d, yyyy',
                )}
              </span>
            )}
            <button
              onClick={handleNext}
              className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              Next →
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-5">
        {/* Progress bar */}
        {plan && (
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all duration-300 rounded-full"
              style={{
                width: `${(daysCompleted / Math.max(plan.days.length, 1)) * 100}%`,
              }}
            />
          </div>
        )}

        {isLoading && (
          <div className="text-center py-16">
            <div className="w-8 h-8 mx-auto mb-3 rounded-full border-2 border-gray-300 border-t-accent animate-spin" />
            <p className="text-sm text-gray-500">Loading plan...</p>
          </div>
        )}

        {error && (
          <div className="text-center py-16 space-y-2">
            <p className="text-gray-900 font-medium">
              No plan found for this week
            </p>
            <p className="text-sm text-gray-500">
              Try navigating to a different week, or generate a new plan.
            </p>
          </div>
        )}

        {plan && (
          <>
            <WeekOverview
              days={plan.days}
              selectedDay={effectiveSelectedDay}
              onSelectDay={setSelectedDay}
            />

            <WeekNarrative
              narrative={plan.narrative}
              days={plan.days}
              phase={phase}
            />

            {selectedDayPlan && <DayDetail day={selectedDayPlan} />}

            <div className="text-center">
              <button
                disabled
                className="px-6 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-400 cursor-not-allowed"
              >
                Reschedule Week (coming soon)
              </button>
            </div>
          </>
        )}

        {!weekStart && (
          <div className="text-center py-16">
            <p className="text-gray-500">
              No schedule generated yet. Please complete onboarding.
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
