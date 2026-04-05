import { useMemo, useState } from 'react'
import { addDays, subDays, format, differenceInWeeks, parseISO } from 'date-fns'
import { usePlan } from '../../hooks/usePlan'
import { useCheckIn } from '../../hooks/useCheckIn'
import { useConfidence } from '../../hooks/useConfidence'
import { useRebalance } from '../../hooks/useRebalance'
import { useUserStore } from '../../store/userStore'
import { getStudyPhase } from '../../lib/constants'
import { getTodayStr, getDebugDate } from '../../lib/debug'
import { WeekOverview } from './WeekOverview'
import { WeekNarrative } from './WeekNarrative'
import { DayDetail } from './DayDetail'
import { ConfidencePanel } from './ConfidencePanel'
import { RebalanceInsight } from './RebalanceInsight'

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
  const checkIn = useCheckIn()
  const { data: confidences = [] } = useConfidence(userId)
  const rebalance = useRebalance()
  const [showRebalance, setShowRebalance] = useState(false)
  const [recoveryDays, setRecoveryDays] = useState(3)
  const [rebalanceError, setRebalanceError] = useState<string | null>(null)
  const [rebalanceNarrative, setRebalanceNarrative] = useState<string | null>(null)
  const [rebalanceStep, setRebalanceStep] = useState<'config' | 'confirm'>('config')

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

  const todayStr = getTodayStr()

  const phase = useMemo(() => {
    if (!prelimsDate) return 'Foundation'
    const todayDate = new Date(todayStr + 'T00:00:00')
    const days = Math.max(
      0,
      Math.ceil(
        (parseISO(prelimsDate).getTime() - todayDate.getTime()) /
          (1000 * 60 * 60 * 24),
      ),
    )
    return getStudyPhase(days)
  }, [prelimsDate, todayStr])

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
    if (plan.days.some((d) => d.date === todayStr)) return todayStr
    return plan.days[0]?.date ?? null
  }, [plan, selectedDay, todayStr])

  const selectedDayPlan = plan?.days.find(
    (d) => d.date === effectiveSelectedDay,
  )

  const handleCardCheckIn = (
    cardDate: string,
    cardId: string,
    status: 'DONE' | 'PARTIAL' | 'SKIPPED',
    actualDuration?: number,
  ) => {
    if (!userId) return
    checkIn.mutate({
      userId,
      date: cardDate,
      data: {
        cards: [{ card_id: cardId, status, actual_duration: actualDuration }],
        finalize_day: false,
      },
    })
  }

  // Rebalance eligibility: count missed and eligible days
  // Missed = unfinalized past days with no engagement (content not yet dealt with)
  // Finalized days (even all-skipped) are already closed out — don't re-rebalance
  const { missedCount, eligibleCount } = useMemo(() => {
    if (!plan) return { missedCount: 0, eligibleCount: 0 }
    let missed = 0
    let eligible = 0
    for (const day of plan.days) {
      if (day.finalized) continue
      const statuses = new Set(day.cards.map((c) => c.status))
      const hasEngagement = statuses.has('DONE') || statuses.has('PARTIAL')
      if (hasEngagement) continue
      if (day.date < todayStr) {
        missed++
      } else {
        eligible++
      }
    }
    return { missedCount: missed, eligibleCount: eligible }
  }, [plan, todayStr])

  // Past days that are not finalized — will need auto-finalization before rebalance
  // Includes partially done days (DONE/PARTIAL cards stay, remaining PENDING → SKIPPED)
  const unfinalizedPastDays = useMemo(() => {
    if (!plan) return []
    return plan.days.filter((day) => day.date < todayStr && !day.finalized)
  }, [plan, todayStr])

  const canRebalance = missedCount > 0 && eligibleCount > 0

  const triggerRebalance = () => {
    if (!userId || !weekStart) return
    rebalance.mutate(
      {
        userId,
        data: {
          week_start: weekStart,
          recovery_window_days: recoveryDays,
          debug_date: getDebugDate(),
        },
      },
      {
        onSuccess: (res) => {
          if (!res.success) {
            setRebalanceError(res.error || 'Rebalance failed')
          } else {
            setShowRebalance(false)
            setRebalanceError(null)
            setRebalanceStep('config')
            setRebalanceNarrative(res.narrative)
          }
        },
        onError: (err) => {
          setRebalanceError(err instanceof Error ? err.message : 'Rebalance failed')
        },
      },
    )
  }

  const handleRebalance = () => {
    if (!userId || !weekStart) return
    setRebalanceError(null)

    // If there are unfinalized past days, show confirmation step first
    if (unfinalizedPastDays.length > 0 && rebalanceStep === 'config') {
      setRebalanceStep('confirm')
      return
    }

    // Finalize unfinalized past days first, then trigger rebalance
    if (unfinalizedPastDays.length > 0) {
      let remaining = unfinalizedPastDays.length
      for (const day of unfinalizedPastDays) {
        const pendingCards = day.cards
          .filter((c) => c.status === 'PENDING')
          .map((c) => ({ card_id: c.card_id, status: 'SKIPPED' as const }))

        checkIn.mutate(
          {
            userId,
            date: day.date,
            data: { cards: pendingCards, finalize_day: true },
          },
          {
            onSuccess: () => {
              remaining--
              if (remaining === 0) triggerRebalance()
            },
            onError: (err) => {
              setRebalanceError(err instanceof Error ? err.message : 'Failed to finalize days')
            },
          },
        )
      }
    } else {
      triggerRebalance()
    }
  }

  const handleFinalizeDay = (dayDate: string) => {
    if (!userId || !plan) return
    const day = plan.days.find((d) => d.date === dayDate)
    if (!day) return

    // Collect remaining PENDING cards as SKIPPED
    const pendingCards = day.cards
      .filter((c) => c.status === 'PENDING')
      .map((c) => ({ card_id: c.card_id, status: 'SKIPPED' as const }))

    checkIn.mutate({
      userId,
      date: dayDate,
      data: {
        cards: pendingCards,
        finalize_day: true,
      },
    })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-1">
            <div>
              <span className="text-xs font-semibold text-green-700 bg-green-100 px-2 py-0.5 rounded-full uppercase tracking-wider">
                {phase} Phase
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <button
                  onClick={() => setShowRebalance(!showRebalance)}
                  disabled={!canRebalance || rebalance.isPending}
                  className={`px-3 py-1 rounded-lg border text-xs transition ${
                    canRebalance && !rebalance.isPending
                      ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'
                      : 'border-gray-200 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {rebalance.isPending ? 'Rebalancing...' : 'Rebalance Week'}
                </button>
                {showRebalance && canRebalance && (
                  <div className="absolute right-0 top-full mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-lg p-4 z-20">
                    {rebalanceStep === 'confirm' && unfinalizedPastDays.length > 0 ? (
                      <>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-amber-500 text-sm">⚠</span>
                          <span className="text-xs font-semibold text-gray-900">Confirm skip</span>
                        </div>
                        <p className="text-xs text-gray-500 mb-3">
                          {unfinalizedPastDays.length} past day{unfinalizedPastDays.length !== 1 ? 's' : ''} ({unfinalizedPastDays.map((d) => format(new Date(d.date + 'T00:00:00'), 'EEE d')).join(', ')}) will be marked as <span className="font-medium text-gray-700">skipped</span> before rebalancing.
                        </p>
                        {rebalanceError && (
                          <p className="text-xs text-red-600 mb-2">{rebalanceError}</p>
                        )}
                        <div className="flex gap-2">
                          <button
                            onClick={() => setRebalanceStep('config')}
                            className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
                          >
                            Back
                          </button>
                          <button
                            onClick={handleRebalance}
                            disabled={rebalance.isPending || checkIn.isPending}
                            className="flex-1 px-3 py-1.5 rounded-lg bg-amber-500 text-white text-xs font-medium hover:bg-amber-600 disabled:opacity-50"
                          >
                            {rebalance.isPending || checkIn.isPending ? 'Working...' : 'Skip & Rebalance'}
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="text-xs text-gray-500 mb-3">
                          {missedCount} missed day{missedCount !== 1 ? 's' : ''} detected.
                          Redistribute into upcoming days.
                        </p>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Recovery window (days)
                        </label>
                        <input
                          type="range"
                          min={1}
                          max={Math.min(eligibleCount, 7)}
                          value={Math.min(recoveryDays, eligibleCount)}
                          onChange={(e) => setRecoveryDays(Number(e.target.value))}
                          className="w-full mb-1"
                        />
                        <div className="flex justify-between text-xs text-gray-400 mb-3">
                          <span>1 day</span>
                          <span className="font-medium text-gray-700">
                            {Math.min(recoveryDays, eligibleCount)} day{Math.min(recoveryDays, eligibleCount) !== 1 ? 's' : ''}
                          </span>
                          <span>{Math.min(eligibleCount, 7)} days</span>
                        </div>
                        {rebalanceError && (
                          <p className="text-xs text-red-600 mb-2">{rebalanceError}</p>
                        )}
                        <div className="flex gap-2">
                          <button
                            onClick={() => { setShowRebalance(false); setRebalanceError(null); setRebalanceStep('config') }}
                            className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleRebalance}
                            disabled={rebalance.isPending}
                            className="flex-1 px-3 py-1.5 rounded-lg bg-amber-500 text-white text-xs font-medium hover:bg-amber-600 disabled:opacity-50"
                          >
                            {rebalance.isPending ? 'Working...' : 'Rebalance'}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
              {getDebugDate() && (
                <span className="text-[10px] font-mono text-orange-500 bg-orange-50 px-1.5 py-0.5 rounded">
                  debug: {todayStr}
                </span>
              )}
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
              {daysCompleted}/{plan?.days.length ?? 7} days done
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

      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* Progress bar */}
        {plan && (
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-5">
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
          <div className="flex gap-5">
            {/* Left column — Schedule Insights + Confidence */}
            <div className="w-72 flex-shrink-0">
              <div className="sticky top-6 space-y-4">
                {rebalanceNarrative && (
                  <RebalanceInsight
                    narrative={rebalanceNarrative}
                    onDismiss={() => setRebalanceNarrative(null)}
                  />
                )}
                <WeekNarrative
                  narrative={plan.narrative}
                  days={plan.days}
                  phase={phase}
                />
                <ConfidencePanel confidences={confidences} />
              </div>
            </div>

            {/* Right column — Week overview + Day detail */}
            <div className="flex-1 min-w-0 space-y-5">
              <WeekOverview
                days={plan.days}
                selectedDay={effectiveSelectedDay}
                onSelectDay={setSelectedDay}
                todayStr={todayStr}
              />
              {selectedDayPlan && (
                <DayDetail
                  day={selectedDayPlan}
                  onCardCheckIn={(cardId, status, actualDuration) =>
                    handleCardCheckIn(selectedDayPlan.date, cardId, status, actualDuration)
                  }
                  onFinalizeDay={() => handleFinalizeDay(selectedDayPlan.date)}
                  isCheckingIn={checkIn.isPending}
                />
              )}
            </div>
          </div>
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
