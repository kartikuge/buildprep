import type { RebalanceRequest, RebalanceResponse } from '../types'
import { apiFetch } from './client'

export function submitRebalance(
  userId: string,
  data: RebalanceRequest,
): Promise<RebalanceResponse> {
  return apiFetch(`/users/${userId}/plan/rebalance`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
