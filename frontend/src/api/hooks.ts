import { useQuery } from '@tanstack/react-query'
import { apiGet, type HealthResponse, type UsageResponse } from './client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
    refetchInterval: 30_000,
  })
}

export function useUsage() {
  return useQuery({
    queryKey: ['usage'],
    queryFn: () => apiGet<UsageResponse>('/usage'),
  })
}
