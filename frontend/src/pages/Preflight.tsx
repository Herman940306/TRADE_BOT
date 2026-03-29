import { useQuery } from '@tanstack/react-query';
import { fetchPreflight } from '../lib/api';
import { cn } from '../lib/utils';

export function Preflight() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['preflight'],
    queryFn: fetchPreflight,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Preflight Checklist</h2>
        <button
          onClick={() => refetch()}
          className="rounded border border-gray-700 px-3 py-1 text-sm text-gray-400 hover:bg-gray-800"
        >
          Refresh
        </button>
      </div>

      {isLoading && <p className="text-gray-500">Running checks...</p>}
      {error && <p className="text-red-400">Error: {(error as Error).message}</p>}

      {data && (
        <>
          {/* Overall status */}
          <div
            className={cn(
              'card border-2',
              data.ready ? 'border-green-700' : 'border-red-700',
            )}
          >
            <p className="text-lg font-bold">
              {data.ready ? 'GO — All systems ready' : 'NO-GO — Issues detected'}
            </p>
            <p className="text-sm text-gray-400">Mode: {data.mode}</p>
          </div>

          {/* Individual checks */}
          <div className="space-y-2">
            {data.checks.map((c) => (
              <div
                key={c.name}
                className="card flex items-center justify-between"
              >
                <span className="font-medium">{c.name}</span>
                <span
                  className={cn(
                    'rounded-full px-3 py-1 text-xs font-bold',
                    c.status === 'PASS'
                      ? 'bg-green-900/30 text-green-400'
                      : 'bg-red-900/30 text-red-400',
                  )}
                >
                  {c.status}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
