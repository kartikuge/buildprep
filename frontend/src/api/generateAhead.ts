import type { GenerateAheadRequest, GenerateAheadResponse } from '../types'
import { apiFetch } from './client'

export function generateAhead(
  userId: string,
  data: GenerateAheadRequest,
): Promise<GenerateAheadResponse> {
  return apiFetch(`/users/${userId}/plan/generate-ahead`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
