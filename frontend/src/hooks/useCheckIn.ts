import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitCheckIn } from '../api/checkin'
import type { CheckInRequest } from '../types'

interface CheckInParams {
  userId: string
  date: string
  data: CheckInRequest
}

export function useCheckIn() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, date, data }: CheckInParams) =>
      submitCheckIn(userId, date, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan'] })
      queryClient.invalidateQueries({ queryKey: ['confidences'] })
    },
  })
}
