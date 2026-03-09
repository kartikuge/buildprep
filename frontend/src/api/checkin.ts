import type { CheckInRequest, CheckInResponse, TopicConfidence } from '../types'
import { apiFetch } from './client'

export function submitCheckIn(
  userId: string,
  date: string,
  data: CheckInRequest,
): Promise<CheckInResponse> {
  return apiFetch(`/users/${userId}/checkin/${date}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getConfidences(userId: string): Promise<TopicConfidence[]> {
  return apiFetch(`/users/${userId}/confidence`)
}
