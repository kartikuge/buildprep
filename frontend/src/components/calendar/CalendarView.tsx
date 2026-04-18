import { useEffect, useMemo, useState } from 'react'
import { addDays, subDays, format, differenceInWeeks, parseISO } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { getPlan } from '../../api/plans'
import { usePlan } from '../../hooks/usePlan'
import { useCheckIn } from '../../hooks/useCheckIn'
import { useConfidence } from '../../hooks/useConfidence'
import { useRebalance } from '../../hooks/useRebalance'
import { useGenerateAhead } from '../../hooks/useGenerateAhead'
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
  const generateAhead = useGenerateAhead()
  const [showRebalance, setShowRebalance] = useState(false)
  const [recoveryDays, setRecoveryDays] = useState(3)
  const [includeNextWeeks, setIncludeNextWeeks] = useState(0)
  const [rebalanceError, setRebalanceError] = useState<string | null>(null)
  const [rebalanceNarrative, setRebalanceNarrative] = useState<string | null>(null)
  const [rebalanceStep, setRebalanceStep] = useState<'config' | 'confirm'>('config')
  const [autoGenTriggered, setAutoGenTriggered] = useState<string | null>(null)
  const [autoGenBanner, setAutoGenBanner] = useState<string | null>(null)

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

  // Rebalance eligibility: mirrors backend classify_days()
  // - engagement (DONE/PARTIAL on any card) → frozen, ignored here
  // - no engagement + (past OR finalized) → missed (includes all-skipped days user marked complete)
  // - no engagement + today/future + not finalized → eligible recovery target
  const { missedCount, eligibleCount } = useMemo(() => {
    if (!plan) return { missedCount: 0, eligibleCount: 0 }
    let missed = 0
    let eligible = 0
    for (const day of plan.days) {
      const statuses = new Set(day.cards.map((c) => c.status))
      const hasEngagement = statuses.has('DONE') || statuses.has('PARTIAL')
      if (hasEngagement) continue
      if (day.date < todayStr || day.finalized) {
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
    // When extending into future weeks, use all eligible days in this week
    // (the day slider is hidden in that mode — its state is semantically irrelevant).
    const effectiveRecoveryDays =
      includeNextWeeks > 0 ? eligibleCount : Math.min(recoveryDays, eligibleCount)
    rebalance.mutate(
      {
        userId,
        data: {
          week_start: weekStart,
          recovery_window_days: effectiveRecoveryDays,
          debug_date: getDebugDate(),
          include_next_weeks: includeNextWeeks,
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
            setIncludeNextWeeks(0)
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

  // G.1 — Generate Ahead handler
  const handleGenerateAhead = () => {
    if (!userId) return
    generateAhead.mutate(
      {
        userId,
        data: {
          weeks_ahead: 2,
          debug_date: getDebugDate(),
        },
      },
      {
        onSuccess: (res) => {
          const added = res.weeks_generated.length
          if (added > 0) {
            const nowScheduled = Math.min(futureWeeksScheduled + added, maxFutureWeeks)
            setAutoGenBanner(
              `Added ${added} upcoming week${added > 1 ? 's' : ''}. ${nowScheduled}/${maxFutureWeeks} future weeks scheduled.`,
            )
            setTimeout(() => setAutoGenBanner(null), 5000)
          }
        },
      },
    )
  }

  // G.2 — Auto-generation on second-to-last day
  const isSecondToLastDay = useMemo(() => {
    if (!plan) return false
    const sortedDates = plan.days.map((d) => d.date).sort()
    if (sortedDates.length < 2) return false
    return todayStr === sortedDates[sortedDates.length - 2]
  }, [plan, todayStr])

  // Look ahead for already-generated future weeks (drives Generate Ahead counter + auto-gen).
  // Anchor on real today's Monday, NOT the currently-viewed weekStart — the 2-week cap is
  // relative to today, so the counter/enable state must stay stable as the user navigates weeks.
  const realTodayMonday = useMemo(() => {
    const d = new Date(todayStr + 'T00:00:00')
    const dow = d.getDay() // 0 = Sun, 1 = Mon, ...
    const offset = dow === 0 ? -6 : 1 - dow
    return format(addDays(d, offset), 'yyyy-MM-dd')
  }, [todayStr])

  const weekPlus1Start = useMemo(
    () => format(addDays(new Date(realTodayMonday + 'T00:00:00'), 7), 'yyyy-MM-dd'),
    [realTodayMonday],
  )

  const weekPlus2Start = useMemo(
    () => format(addDays(new Date(realTodayMonday + 'T00:00:00'), 14), 'yyyy-MM-dd'),
    [realTodayMonday],
  )

  const { data: weekPlus1Plan } = useQuery({
    queryKey: ['plan', userId, weekPlus1Start],
    queryFn: () => getPlan(userId!, weekPlus1Start!),
    enabled: !!userId && !!weekPlus1Start,
    retry: false,
  })

  const { data: weekPlus2Plan } = useQuery({
    queryKey: ['plan', userId, weekPlus2Start],
    queryFn: () => getPlan(userId!, weekPlus2Start!),
    enabled: !!userId && !!weekPlus2Start,
    retry: false,
  })

  const futureWeeksScheduled = (weekPlus1Plan ? 1 : 0) + (weekPlus2Plan ? 1 : 0)
  const maxFutureWeeks = 2
  const canGenerateAhead = futureWeeksScheduled < maxFutureWeeks

  useEffect(() => {
    if (!isSecondToLastDay || !userId || weekPlus1Plan || autoGenTriggered === weekStart) return
    setAutoGenTriggered(weekStart)
    setAutoGenBanner('Next week is approaching — generating your schedule...')
    generateAhead.mutate(
      {
        userId,
        data: {
          weeks_ahead: 1,
          debug_date: getDebugDate(),
        },
      },
      {
        onSuccess: (res) => {
          if (res.weeks_generated.length > 0) {
            setAutoGenBanner('Next week generated!')
            setTimeout(() => setAutoGenBanner(null), 5000)
          } else {
            setAutoGenBanner(null)
          }
        },
        onError: () => {
          setAutoGenBanner(null)
        },
      },
    )
  }, [isSecondToLastDay, userId, weekPlus1Plan, weekStart, autoGenTriggered])

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
              <button
                onClick={handleGenerateAhead}
                disabled={generateAhead.isPending || !canGenerateAhead}
                title={
                  generateAhead.isPending
                    ? 'Generating…'
                    : canGenerateAhead
                      ? `Plan your next week. Up to ${maxFutureWeeks} weeks ahead of the current week — further weeks auto-generate as you complete the current schedule, so they're shaped by your actual progress.`
                      : `You already have the next ${maxFutureWeeks} weeks scheduled. New weeks will auto-generate as you complete this one — that way they adapt to your confidence scores and what you've missed.`
                }
                className={`px-3 py-1 rounded-lg border text-xs transition flex items-center gap-1.5 ${
                  canGenerateAhead && !generateAhead.isPending
                    ? 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100'
                    : 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
                }`}
              >
                {generateAhead.isPending ? 'Generating...' : 'Generate Ahead'}
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    canGenerateAhead && !generateAhead.isPending
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {futureWeeksScheduled}/{maxFutureWeeks}
                </span>
              </button>
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
                          Choose how far to redistribute.
                        </p>
                        <label className="block text-xs font-medium text-gray-700 mb-1.5">
                          Scope
                        </label>
                        <div className="flex gap-0.5 mb-3 p-0.5 bg-gray-100 rounded-lg">
                          {[0, 1, 2].map((n) => {
                            const disabled =
                              n === 1 ? !weekPlus1Plan :
                              n === 2 ? !(weekPlus1Plan && weekPlus2Plan) :
                              false
                            const label = n === 0 ? 'This week' : `+${n} week${n > 1 ? 's' : ''}`
                            const title = disabled
                              ? `Week +${n} isn't scheduled yet. Use Generate Ahead to add it, then rebalance.`
                              : n === 0
                                ? 'Rebalance only this week'
                                : `Also regenerate the next ${n} week${n > 1 ? 's' : ''} with weak-area priority raised`
                            return (
                              <button
                                key={n}
                                onClick={() => !disabled && setIncludeNextWeeks(n)}
                                disabled={disabled}
                                title={title}
                                className={`flex-1 px-2 py-1 rounded-md text-xs font-medium transition ${
                                  includeNextWeeks === n
                                    ? 'bg-white text-amber-700 shadow-sm'
                                    : disabled
                                      ? 'text-gray-300 cursor-not-allowed'
                                      : 'text-gray-500 hover:text-gray-700'
                                }`}
                              >
                                {label}
                              </button>
                            )
                          })}
                        </div>
                        {includeNextWeeks === 0 ? (
                          <>
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
                          </>
                        ) : (
                          <p className="text-xs text-gray-600 mb-3 px-2.5 py-2 bg-amber-50 rounded-md border border-amber-100">
                            Redistributes across <span className="font-medium">all {eligibleCount} remaining day{eligibleCount !== 1 ? 's' : ''}</span> this week and <span className="font-medium">regenerates the next {includeNextWeeks === 1 ? 'week' : `${includeNextWeeks} weeks`}</span> with weak-area priority raised. The existing plan for {includeNextWeeks === 1 ? 'that week' : 'those weeks'} will be replaced.
                          </p>
                        )}
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

        {autoGenBanner && (
          <div className="mb-4 px-4 py-2 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
            {generateAhead.isPending && (
              <div className="w-4 h-4 rounded-full border-2 border-blue-300 border-t-blue-600 animate-spin" />
            )}
            <span className="text-sm text-blue-700">{autoGenBanner}</span>
            {!generateAhead.isPending && (
              <button
                onClick={() => setAutoGenBanner(null)}
                className="ml-auto text-blue-400 hover:text-blue-600 text-xs"
              >
                Dismiss
              </button>
            )}
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
