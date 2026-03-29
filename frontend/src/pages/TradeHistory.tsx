import { useQuery } from '@tanstack/react-query';
import { fetchTradeHistory } from '../lib/api';
import { useState } from 'react';

export function TradeHistory() {
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading, error } = useQuery({
    queryKey: ['trade-history', page],
    queryFn: () => fetchTradeHistory(limit, page * limit),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Trade History</h2>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-400">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                  <th className="px-3 py-2">Correlation ID</th>
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Side</th>
                  <th className="px-3 py-2">Quantity</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t) => (
                  <tr
                    key={t.correlation_id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30"
                  >
                    <td className="px-3 py-2 font-mono text-xs">{t.correlation_id}</td>
                    <td className="px-3 py-2">{t.symbol}</td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          t.side === 'BUY'
                            ? 'text-green-400'
                            : 'text-red-400'
                        }
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono">{t.quantity ?? '—'}</td>
                    <td className="px-3 py-2">{t.status}</td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">
              Showing {page * limit + 1}–{Math.min((page + 1) * limit, data.total)} of{' '}
              {data.total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="rounded border border-gray-700 px-3 py-1 text-gray-400 hover:bg-gray-800 disabled:opacity-30"
              >
                Prev
              </button>
              <button
                disabled={(page + 1) * limit >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded border border-gray-700 px-3 py-1 text-gray-400 hover:bg-gray-800 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
