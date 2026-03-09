import { useQuery } from '@tanstack/react-query'
import { getConfidences } from '../api/checkin'

export function useConfidence(userId: string | null) {
  return useQuery({
    queryKey: ['confidences', userId],
    queryFn: () => getConfidences(userId!),
    enabled: !!userId,
  })
}
