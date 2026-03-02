import type { OnboardRequest, OnboardResponse } from '../types'
import { apiFetch } from './client'

export function onboard(data: OnboardRequest): Promise<OnboardResponse> {
  return apiFetch('/users/onboard', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
