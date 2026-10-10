import React from 'react';
import { AnalyzeResponse, SafetyAlert } from '../lib/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface OverviewProps {
  result: AnalyzeResponse;
  onIssueClick: (aspect: string, polarity: string) => void;
}

export const Overview: React.FC<OverviewProps> = ({ result, onIssueClick }) => {
  const hasRating = result.avg_rating !== null;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Safety Banner */}
      {result.safety_alerts.length > 0 && (
        <div className="safety-banner">
          <div className="max-w-6xl mx-auto">
            <h3 className="font-bold mb-2">SAFETY ALERT - {result.safety_alerts.length} case(s)</h3>
            <div className="space-y-1 text-sm">
              {result.safety_alerts.slice(0, 3).map((alert) => (
                <p key={alert.clause_id}>{alert.text}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className={`pt-${result.safety_alerts.length > 0 ? '32' : '0'}`}>
        <h2 className="text-2xl font-bold mb-6">Analysis Overview</h2>

        {/* Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-600 text-sm">Reviews</p>
            <p className="text-3xl font-bold">{result.review_count}</p>
          </div>

          {hasRating && (
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-gray-600 text-sm">Average Rating</p>
              <p className="text-3xl font-bold">{result.avg_rating?.toFixed(2)}</p>
              <p className="text-xs text-gray-500">out of 5</p>
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-600 text-sm">Negative Reviews</p>
            <p className="text-3xl font-bold">{(result.pct_negative * 100).toFixed(0)}%</p>
            <p className="text-xs text-gray-500">{Math.round(result.review_count * result.pct_negative)} reviews</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-600 text-sm">Languages</p>
            <p className="text-3xl font-bold">{Object.keys(result.languages).length}</p>
            <p className="text-xs text-gray-500">{Object.entries(result.languages).map(([l, c]) => `${l}: ${c}`).join(', ')}</p>
          </div>
        </div>

        {/* Warnings */}
        {result.warnings.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-8">
            <p className="font-semibold text-yellow-900 mb-2">Warnings:</p>
            <ul className="list-disc list-inside space-y-1 text-sm text-yellow-800">
              {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}

        {/* Top Issues */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold mb-4">Top Issues to Fix (Ranked by Frequency & Impact)</h3>

          {result.top_issues.length === 0 ? (
            <p className="text-gray-500">No negative issues detected.</p>
          ) : (
            <div className="space-y-3">
              {result.top_issues.map((issue, i) => (
                <div
                  key={`${issue.aspect}-${issue.polarity}`}
                  onClick={() => onIssueClick(issue.aspect || 'other', issue.polarity)}
                  className="border border-gray-200 rounded-lg p-4 cursor-pointer hover:bg-gray-50 transition"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-lg">
                        #{i + 1} {issue.aspect || 'Other'} {issue.confidence_label === 'low' && '⚠️'}
                      </h4>
                      <p className="text-sm text-gray-600">
                        {issue.mentions} mentions ({(issue.pct_negative * 100).toFixed(0)}% negative)
                      </p>
                    </div>
                    {issue.damage !== null && (
                      <div className="text-right">
                        <p className="text-sm text-gray-500">Estimated impact</p>
                        <p className="text-xl font-bold text-red-600">-{issue.damage.toFixed(1)} ⭐</p>
                      </div>
                    )}
                  </div>
                  {issue.confidence_label === 'low' && (
                    <p className="text-xs text-orange-600">Low confidence (fewer than 30 mentions)</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-sm text-gray-500 mt-6">Click an issue to see supporting reviews</p>
      </div>
    </div>
  );
};
