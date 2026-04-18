import { useMutation, useQueryClient } from '@tanstack/react-query'
import { generateAhead } from '../api/generateAhead'
import type { GenerateAheadRequest } from '../types'

interface GenerateAheadParams {
  userId: string
  data: GenerateAheadRequest
}

export function useGenerateAhead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, data }: GenerateAheadParams) =>
      generateAhead(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan'] })
    },
  })
}
