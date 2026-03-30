import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as api from "@/services/api"
import type { ApproveRequest, RejectRequest, GuardianUnlockRequest } from "@/types/api"

// System queries
export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: api.getSystemStatus,
    refetchInterval: 10_000,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 10_000,
  })
}

// Budget queries
export function useBudgetStatus() {
  return useQuery({
    queryKey: ["budget-status"],
    queryFn: api.getBudgetStatus,
    refetchInterval: 10_000,
  })
}

// Guardian queries
export function useGuardianStatus() {
  return useQuery({
    queryKey: ["guardian-status"],
    queryFn: api.getGuardianStatus,
    refetchInterval: 5_000,
  })
}

export function useUnlockGuardian() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: GuardianUnlockRequest) => api.unlockGuardian(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["guardian-status"] })
      qc.invalidateQueries({ queryKey: ["system-status"] })
    },
  })
}

// HITL queries
export function usePendingApprovals() {
  return useQuery({
    queryKey: ["hitl-pending"],
    queryFn: api.getPendingApprovals,
    refetchInterval: 5_000,
  })
}

export function useApproveTrade() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tradeId, req }: { tradeId: string; req: ApproveRequest }) =>
      api.approveTrade(tradeId, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hitl-pending"] })
      qc.invalidateQueries({ queryKey: ["trade-lifecycle"] })
    },
  })
}

export function useRejectTrade() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tradeId, req }: { tradeId: string; req: RejectRequest }) =>
      api.rejectTrade(tradeId, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hitl-pending"] })
      qc.invalidateQueries({ queryKey: ["trade-lifecycle"] })
    },
  })
}

// Trade Lifecycle queries
export function useTradeLifecycleStatus() {
  return useQuery({
    queryKey: ["trade-lifecycle", "status"],
    queryFn: api.getTradeLifecycleStatus,
    refetchInterval: 10_000,
  })
}

export function useTradesByState(state: string) {
  return useQuery({
    queryKey: ["trade-lifecycle", "trades", state],
    queryFn: () => api.getTradesByState(state),
    enabled: !!state,
  })
}

// RGI queries
export function useRGIStatus() {
  return useQuery({
    queryKey: ["rgi-status"],
    queryFn: api.getRGIStatus,
    refetchInterval: 30_000,
  })
}

// Strategy queries
export function useStrategyStatus() {
  return useQuery({
    queryKey: ["strategy-status"],
    queryFn: api.getStrategyStatus,
    refetchInterval: 30_000,
  })
}

// Learning queries
export function useLearningCurricula() {
  return useQuery({
    queryKey: ["learning-curricula"],
    queryFn: api.getLearningCurricula,
    refetchInterval: 30_000,
  })
}

export function useBayesianBeliefs() {
  return useQuery({
    queryKey: ["bayesian-beliefs"],
    queryFn: api.getBayesianBeliefs,
    refetchInterval: 30_000,
  })
}

export function usePatternFingerprints() {
  return useQuery({
    queryKey: ["pattern-fingerprints"],
    queryFn: api.getPatternFingerprints,
    refetchInterval: 30_000,
  })
}

// Strategy variant queries
export function useStrategyVariants() {
  return useQuery({
    queryKey: ["strategy-variants"],
    queryFn: api.getStrategyVariants,
    refetchInterval: 30_000,
  })
}

export function useSandboxTrades() {
  return useQuery({
    queryKey: ["sandbox-trades"],
    queryFn: api.getSandboxTrades,
    refetchInterval: 15_000,
  })
}
