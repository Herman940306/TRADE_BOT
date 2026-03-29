import { useQuery } from '@tanstack/react-query';
import { fetchDecisionSnapshots } from '../lib/api';
import { formatZAR } from '../lib/utils';

export function DecisionSnapshots() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['decision-snapshots'],
    queryFn: () => fetchDecisionSnapshots(50),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Decision Forensics</h2>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-400">Error: {(error as Error).message}</p>}

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Mind State</th>
                <th className="px-3 py-2">Regime</th>
                <th className="px-3 py-2">Strategy</th>
                <th className="px-3 py-2">Size (ZAR)</th>
                <th className="px-3 py-2">Guardian</th>
                <th className="px-3 py-2">Operator</th>
                <th className="px-3 py-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {data.snapshots.map((s) => (
                <tr
                  key={s.snapshot_id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30"
                >
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-gray-400">
                    {s.created_at
                      ? new Date(s.created_at).toLocaleString()
                      : '—'}
                  </td>
                  <td className="px-3 py-2 font-mono">{s.confidence}</td>
                  <td className="px-3 py-2">{s.mind_state}</td>
                  <td className="px-3 py-2">{s.regime}</td>
                  <td className="px-3 py-2">{s.strategy_name}</td>
                  <td className="px-3 py-2 font-mono">
                    {formatZAR(s.final_size_zar)}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        s.guardian_status === 'PASS'
                          ? 'text-green-400'
                          : 'text-red-400'
                      }
                    >
                      {s.guardian_status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{s.operator_decision}</td>
                  <td className="px-3 py-2 font-mono">
                    {s.outcome_pnl_zar ? (
                      <span
                        className={
                          s.outcome_pnl_zar.startsWith('-')
                            ? 'text-red-400'
                            : 'text-green-400'
                        }
                      >
                        {formatZAR(s.outcome_pnl_zar)}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-gray-500">
            Total snapshots: {data.total}
          </p>
        </div>
      )}
    </div>
  );
}
