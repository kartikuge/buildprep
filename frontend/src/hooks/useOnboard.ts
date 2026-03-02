import { useMutation } from '@tanstack/react-query'
import { onboard } from '../api/users'
import type { OnboardRequest } from '../types'

export function useOnboard() {
  return useMutation({
    mutationFn: (data: OnboardRequest) => onboard(data),
  })
}
