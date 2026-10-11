import { FC } from 'react';
import { AnalyzeResponse } from '../lib/api';
import { SpotlightCard } from './SpotlightCard';

interface OverviewProps {
  result: AnalyzeResponse;
  onIssueClick: (aspect: string, polarity: string) => void;
}

export const Overview: FC<OverviewProps> = ({ result, onIssueClick }) => {
  const hasRating = result.avg_rating !== null;

  return (
    <div className="mx-auto max-w-7xl">
      {/* Safety Banner */}
      {result.safety_alerts.length > 0 && (
        <div className="safety-banner mb-5 rounded">
          <div>
            <h3 className="mb-2 font-semibold uppercase tracking-wide">Safety & compliance alerts · {result.safety_alerts.length} case(s)</h3>
            <div className="space-y-1 text-sm">
              {result.safety_alerts.slice(0, 3).map((alert) => (
                <p key={alert.clause_id}>{alert.text}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      <div>
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Operational intelligence</p>
            <h2 className="text-2xl font-semibold tracking-tight">Analysis Overview</h2>
          </div>
          <span className="hidden font-mono text-xs text-[#737686] sm:block">{result.mode} analysis · {result.processing_ms} ms</span>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="enterprise-card p-5">
            <p className="text-xs uppercase tracking-wide text-[#737686]">Analyzed corpus</p>
            <p className="tabular-nums mt-2 text-3xl font-semibold">{result.review_count.toLocaleString()}</p>
            <p className="mt-1 text-xs text-[#737686]">Total reviews</p>
          </div>

          {hasRating && (
            <div className="enterprise-card p-5">
              <p className="text-xs uppercase tracking-wide text-[#737686]">Average rating</p>
              <p className="tabular-nums mt-2 text-3xl font-semibold">{result.avg_rating?.toFixed(2)}<span className="ml-1 text-base font-normal text-[#737686]">/ 5.00</span></p>
              <p className="mt-1 text-xs text-[#737686]">{result.rating_source === 'pseudo' ? 'Sentiment-based estimate' : 'Provided rating data'}</p>
            </div>
          )}

          <div className="enterprise-card p-5">
            <p className="text-xs uppercase tracking-wide text-[#737686]">Negative review share</p>
            <p className="tabular-nums mt-2 text-3xl font-semibold text-[#ba1a1a]">{(result.pct_negative * 100).toFixed(1)}%</p>
            <p className="mt-1 text-xs text-[#737686]">{Math.round(result.review_count * result.pct_negative).toLocaleString()} reviews</p>
          </div>

          <div className="enterprise-card p-5">
            <p className="text-xs uppercase tracking-wide text-[#737686]">Language distribution</p>
            <p className="tabular-nums mt-2 text-3xl font-semibold">{Object.keys(result.languages).length}</p>
            <p className="mt-1 truncate text-xs text-[#737686]">{Object.entries(result.languages).map(([l, c]) => `${l} ${c}`).join(' / ')}</p>
          </div>
        </div>

        {/* Warnings */}
        {result.warnings.length > 0 && (
          <div className="mb-8 rounded border border-yellow-200 bg-yellow-50 p-4">
            <p className="mb-2 font-semibold text-yellow-900">Warnings:</p>
            <ul className="list-disc list-inside space-y-1 text-sm text-yellow-800">
              {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}

        {/* Top Issues */}
        <div className="enterprise-card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-[#e0e3e5] p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-base font-semibold">Impact prioritization grid</h3>
              <span className="font-mono text-xs text-[#737686]">{result.top_issues.length} primary clusters identified</span>
            </div>
            <button type="button" className="rounded border border-[#e0e3e5] bg-white px-3 py-2 text-xs font-medium text-[#515f74] hover:bg-[#f2f4f6]">
              ↓ Export CSV
            </button>
          </div>

          {result.top_issues.length === 0 ? (
            <p className="p-5 text-gray-500">No negative issues detected.</p>
          ) : (
            <div className="overflow-x-auto">
              <div className="grid min-w-[760px] grid-cols-[44px_minmax(220px,1fr)_110px_120px_110px_150px] bg-[#f2f4f6] px-4 py-3 text-[10px] font-semibold uppercase tracking-wide text-[#515f74]">
                <span>#</span><span>Issue cluster name</span><span>Mentions</span><span>Negative share</span><span>Rating drag</span><span>Actions</span>
              </div>
              {result.top_issues.map((issue, i) => (
                <SpotlightCard key={`${issue.aspect}-${issue.polarity}`} className="border-b border-gray-200 last:border-b-0">
                  <div className="grid min-w-[760px] grid-cols-[44px_minmax(220px,1fr)_110px_120px_110px_150px] items-center gap-2 px-4 py-3 transition hover:bg-[#f2f4f6]">
                    <span className="font-mono text-xs text-[#737686]">{String(i + 1).padStart(2, '0')}</span>
                    <button type="button" onClick={() => onIssueClick(issue.aspect || 'other', issue.polarity)} className="text-left">
                      <span className="block font-semibold">{issue.aspect || 'Other'} {issue.confidence_label === 'low' && '⚠️'}</span>
                      <span className="block truncate text-xs text-gray-600">{issue.mentions} mentions · clustered problem statement</span>
                    </button>
                    <span className="font-mono text-sm">{issue.mentions.toLocaleString()}</span>
                    <span className="font-mono text-sm text-[#ba1a1a]">{(issue.pct_negative * 100).toFixed(1)}%</span>
                    <span className="rounded bg-red-50 px-2 py-1 font-mono text-xs text-red-700">{issue.damage !== null ? `-${issue.damage.toFixed(2)} ★` : '—'}</span>
                    <button type="button" onClick={() => onIssueClick(issue.aspect || 'other', issue.polarity)} className="w-fit rounded bg-[#004ac6] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#003ea8]">Details →</button>
                  </div>
                </SpotlightCard>
              ))}
            </div>
          )}
        </div>

        <p className="text-sm text-gray-500 mt-6">Click an issue to see supporting reviews</p>
      </div>
    </div>
  );
};
