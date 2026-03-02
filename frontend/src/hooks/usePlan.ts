import { useQuery } from '@tanstack/react-query'
import { getPlan } from '../api/plans'

export function usePlan(userId: string | null, weekStart: string | null) {
  return useQuery({
    queryKey: ['plan', userId, weekStart],
    queryFn: () => getPlan(userId!, weekStart!),
    enabled: !!userId && !!weekStart,
  })
}
