import { useState } from 'react'
import { MAINS_SUBJECTS, EXAM_CYCLES } from '../../lib/constants'
import { getDebugDate } from '../../lib/debug'
import { useOnboard } from '../../hooks/useOnboard'
import { useUserStore } from '../../store/userStore'
import { ProgressDots } from './ProgressDots'
import { StepWelcome } from './StepWelcome'
import { StepOptionalSubject } from './StepOptionalSubject'
import { StepExamDate } from './StepExamDate'
import { StepStudyHours } from './StepStudyHours'
import { StepConfidence } from './StepConfidence'
import { StepReview } from './StepReview'
import type { OnboardRequest } from '../../types'

const TOTAL_STEPS = 6
const STEP_LABELS = ['Welcome', 'Optional Subject', 'Exam Cycle', 'Study Hours', 'Subjects', 'Review']

export function OnboardingWizard() {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [optionalSubject, setOptionalSubject] = useState<string | null>(null)
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null)
  const [hours, setHours] = useState(6)
  const [preferredTimes, setPreferredTimes] = useState<string[]>(['morning'])
  const [confidences, setConfidences] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {}
    MAINS_SUBJECTS.forEach((s) => (init[s] = 3))
    init['CSAT'] = 3
    return init
  })

  const { mutate, isPending } = useOnboard()
  const setUser = useUserStore((s) => s.setUser)

  const handleConfidenceChange = (subject: string, value: number) => {
    setConfidences((prev) => ({ ...prev, [subject]: value }))
  }

  const handleSubmit = () => {
    const cycle = EXAM_CYCLES.find((c) => c.id === selectedCycleId)

    const payload: OnboardRequest = {
      display_name: name.trim(),
      optional_subject: optionalSubject,
      stage: 'both',
      prelims_date: cycle?.prelimsDate ?? null,
      mains_date: cycle?.mainsDate ?? null,
      available_hours_per_day: hours,
      subject_confidences: confidences,
      debug_date: getDebugDate(),
    }

    mutate(payload, {
      onSuccess: (data) => {
        setUser(
          data.user_id,
          data.profile.display_name,
          data.plan?.week_start ?? null,
          data.profile.prelims_date ?? null,
          data.plan?.week_start ?? null,
        )
      },
    })
  }

  const next = () => setStep((s) => Math.min(s + 1, TOTAL_STEPS - 1))
  const back = () => setStep((s) => Math.max(s - 1, 0))

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="w-full h-1 bg-gray-200">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
        />
      </div>

      <ProgressDots current={step} />

      <div className="flex-1 flex items-start justify-center px-4 pt-4 pb-16">
        <div className="w-full max-w-lg">
          {step === 0 && (
            <StepWelcome name={name} onNameChange={setName} onNext={next} />
          )}
          {step === 1 && (
            <StepOptionalSubject
              optionalSubject={optionalSubject}
              onSubjectChange={setOptionalSubject}
              onNext={next}
              onBack={back}
            />
          )}
          {step === 2 && (
            <StepExamDate
              selectedCycleId={selectedCycleId}
              onCycleChange={setSelectedCycleId}
              onNext={next}
              onBack={back}
            />
          )}
          {step === 3 && (
            <StepStudyHours
              hours={hours}
              preferredTimes={preferredTimes}
              onHoursChange={setHours}
              onTimesChange={setPreferredTimes}
              onNext={next}
              onBack={back}
            />
          )}
          {step === 4 && (
            <StepConfidence
              confidences={confidences}
              optionalSubject={optionalSubject}
              onConfidenceChange={handleConfidenceChange}
              onNext={next}
              onBack={back}
            />
          )}
          {step === 5 && (
            <StepReview
              name={name}
              selectedCycleId={selectedCycleId}
              optionalSubject={optionalSubject}
              hours={hours}
              preferredTimes={preferredTimes}
              confidences={confidences}
              onBack={back}
              onSubmit={handleSubmit}
              isSubmitting={isPending}
            />
          )}
        </div>
      </div>

      <div className="text-center py-4 text-xs tracking-widest text-gray-400 uppercase">
        Step {step + 1} of {TOTAL_STEPS} — {STEP_LABELS[step]}
      </div>
    </div>
  )
}
