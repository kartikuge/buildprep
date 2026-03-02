import type { WeeklyPlan } from '../types'
import { apiFetch } from './client'

export function getPlan(userId: string, weekStart: string): Promise<WeeklyPlan> {
  return apiFetch(`/users/${userId}/plan?week_start=${weekStart}`)
}

export function generatePlan(
  userId: string,
  weekStart?: string,
): Promise<WeeklyPlan> {
  return apiFetch(`/users/${userId}/plan/generate`, {
    method: 'POST',
    body: JSON.stringify({ week_start: weekStart ?? null }),
  })
}
