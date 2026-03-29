import { useQuery } from '@tanstack/react-query';
import { fetchLearningStatus, fetchOperatorAnalytics } from '../lib/api';
import { cn, formatZAR } from '../lib/utils';

function MindStateBadge({ state }: { state: string }) {
  const cls =
    state === 'CALM'
      ? 'badge-calm'
      : state === 'ALERT'
        ? 'badge-alert'
        : 'badge-defensive';
  return <span className={cls}>{state}</span>;
}

export function Dashboard() {
  const learning = useQuery({
    queryKey: ['learning-status'],
    queryFn: fetchLearningStatus,
    refetchInterval: 15_000,
  });

  const analytics = useQuery({
    queryKey: ['operator-analytics'],
    queryFn: fetchOperatorAnalytics,
  });

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">System Overview</h2>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Mind State */}
        <div className="card">
          <p className="text-xs text-gray-500">Mind State</p>
          <div className="mt-1">
            {learning.data ? (
              <MindStateBadge state={learning.data.mind_state} />
            ) : (
              <span className="text-gray-600">—</span>
            )}
          </div>
        </div>

        {/* Curriculum Phase */}
        <div className="card">
          <p className="text-xs text-gray-500">Curriculum</p>
          <p className="mt-1 text-lg font-semibold">
            {learning.data?.curriculum_name ?? '—'}
          </p>
          <p className="text-xs text-gray-500">
            Phase {learning.data?.curriculum_phase ?? '—'}
          </p>
        </div>

        {/* Budget */}
        <div className="card">
          <p className="text-xs text-gray-500">Confidence Budget</p>
          <p className="mt-1 font-mono text-lg">
            {learning.data?.budget_remaining ?? '—'}
            <span className="text-gray-500">
              {' '}
              / {learning.data?.budget_total ?? '—'}
            </span>
          </p>
        </div>

        {/* Operator Accuracy */}
        <div className="card">
          <p className="text-xs text-gray-500">Operator Accuracy</p>
          <p className="mt-1 font-mono text-lg">
            {analytics.data?.accuracy
              ? `${(parseFloat(analytics.data.accuracy) * 100).toFixed(1)}%`
              : '—'}
          </p>
          <p className="text-xs text-gray-500">
            {analytics.data
              ? `${analytics.data.approvals} approved / ${analytics.data.rejections} rejected`
              : ''}
          </p>
        </div>
      </div>

      {/* Quick stats row */}
      {analytics.data && (
        <div className="card">
          <h3 className="mb-3 text-sm font-semibold text-gray-400">
            Operator Performance
          </h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-500">Total Decisions</p>
              <p className="text-lg font-bold">{analytics.data.total_decisions}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Timeouts</p>
              <p className="text-lg font-bold">{analytics.data.timeouts}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Value Add</p>
              <p className={cn('text-lg font-bold font-mono')}>
                {formatZAR(analytics.data.total_value_add_zar)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
