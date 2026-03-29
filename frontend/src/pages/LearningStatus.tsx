import { useQuery } from '@tanstack/react-query';
import { fetchLearningStatus, fetchRegimeStatus } from '../lib/api';

export function LearningStatus() {
  const learning = useQuery({
    queryKey: ['learning-status'],
    queryFn: fetchLearningStatus,
    refetchInterval: 15_000,
  });

  const regimes = useQuery({
    queryKey: ['regime-status'],
    queryFn: fetchRegimeStatus,
  });

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Intelligence Layer</h2>

      {/* Learning overview */}
      {learning.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="card">
            <p className="text-xs text-gray-500">Mind State</p>
            <p className="mt-1 text-2xl font-bold">{learning.data.mind_state}</p>
          </div>
          <div className="card">
            <p className="text-xs text-gray-500">Curriculum</p>
            <p className="mt-1 text-2xl font-bold">
              Phase {learning.data.curriculum_phase}
            </p>
            <p className="text-sm text-gray-400">{learning.data.curriculum_name}</p>
          </div>
          <div className="card">
            <p className="text-xs text-gray-500">Confidence Budget</p>
            <p className="mt-1 font-mono text-2xl font-bold">
              {learning.data.budget_remaining ?? '—'}
            </p>
            <p className="text-sm text-gray-400">
              of {learning.data.budget_total ?? '—'} daily
            </p>
          </div>
        </div>
      )}

      {/* Regime status */}
      {regimes.data && regimes.data.current.length > 0 && (
        <div className="card">
          <h3 className="mb-3 text-sm font-semibold text-gray-400">
            Current Regime Classification
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Regime</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2">As Of</th>
                </tr>
              </thead>
              <tbody>
                {regimes.data.current.map((r) => (
                  <tr
                    key={r.symbol}
                    className="border-b border-gray-800/50"
                  >
                    <td className="px-3 py-2 font-mono">{r.symbol}</td>
                    <td className="px-3 py-2">{r.regime}</td>
                    <td className="px-3 py-2 font-mono">{r.confidence}</td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {r.as_of ? new Date(r.as_of).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
