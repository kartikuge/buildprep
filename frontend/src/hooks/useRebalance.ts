import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitRebalance } from '../api/rebalance'
import type { RebalanceRequest } from '../types'

interface RebalanceParams {
  userId: string
  data: RebalanceRequest
}

export function useRebalance() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, data }: RebalanceParams) =>
      submitRebalance(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan'] })
      queryClient.invalidateQueries({ queryKey: ['confidences'] })
    },
  })
}
