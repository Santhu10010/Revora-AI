import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AnalyzeResponse, SimulationResponse, api } from '../lib/api';

interface SimulatorProps {
  result: AnalyzeResponse;
}

const clampToZeroToOne = (value: number) => Math.min(1, Math.max(0, value));

export const Simulator: React.FC<SimulatorProps> = ({ result }) => {
  const issues = useMemo(() => result.top_issues.slice(0, 5), [result.top_issues]);
  const [fixes, setFixes] = useState<Record<string, number>>({});
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const nextFixes: Record<string, number> = {};
    issues.forEach((issue, index) => {
      const key = issue.aspect ?? `other-${index}`;
      nextFixes[key] = fixes[key] ?? 0;
    });
    setFixes((current) => {
      const unchanged = Object.keys(nextFixes).length === Object.keys(current).length
        && Object.entries(nextFixes).every(([key, value]) => current[key] === value);
      return unchanged ? current : nextFixes;
    });
  }, [fixes, issues]);

  useEffect(() => {
    if (issues.length === 0) {
      setSimulation(null);
      return;
    }

    const timer = window.setTimeout(async () => {
      try {
        setLoading(true);
        setError(null);
        const payload = await api.simulate(result.analysis_id, Object.fromEntries(
          Object.entries(fixes).map(([key, value]) => [key, clampToZeroToOne(value)]),
        ));
        setSimulation(payload);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to simulate impact';
        setError(message);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(timer);
  }, [fixes, issues, result.analysis_id]);

  const currentAvg = result.avg_rating ?? 0;
  const projectedAvg = simulation?.projected_avg ?? currentAvg;
  const chartData = [
    { name: 'Before', value: currentAvg },
    { name: 'After', value: projectedAvg },
  ];

  const applyPreset = () => {
    const next: Record<string, number> = {};
    issues.forEach((issue, index) => {
      const key = issue.aspect ?? `other-${index}`;
      next[key] = index < 3 ? 0.5 : 0;
    });
    setFixes(next);
  };

  const resetFixes = () => {
    const next: Record<string, number> = {};
    issues.forEach((issue, index) => {
      next[issue.aspect ?? `other-${index}`] = 0;
    });
    setFixes(next);
  };

  if (issues.length === 0) {
    return (
      <div className="enterprise-card mx-auto max-w-3xl p-8">
        <h2 className="mb-4 text-2xl font-semibold">Simulator</h2>
        <p className="text-[#737686]">No negative issues are available for simulation yet.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="enterprise-card p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Scenario planning</p>
            <h2 className="text-2xl font-semibold">Rating outcome simulator</h2>
            <p className="text-sm text-[#737686]">Adjust each issue and preview the projected average rating.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={applyPreset} className="rounded border border-[#004ac6] px-3 py-2 text-sm font-medium text-[#004ac6] hover:bg-[#eeefff]">Fix top 3</button>
            <button type="button" onClick={resetFixes} className="rounded border border-[#e0e3e5] px-3 py-2 text-sm font-medium text-[#515f74] hover:bg-[#f2f4f6]">Reset</button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="enterprise-card p-6">
          <h3 className="text-lg font-semibold mb-4">Issue impact</h3>
          <div className="space-y-4">
            {issues.map((issue, index) => {
              const key = issue.aspect ?? `other-${index}`;
              const sliderValue = fixes[key] ?? 0;
              return (
                <div key={key} className="rounded border border-[#e0e3e5] p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-semibold">{issue.aspect ?? 'Other'}</p>
                        {issue.confidence_label === 'low' && <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-medium text-orange-800">Low confidence</span>}
                      </div>
                      <p className="text-xs text-gray-500">{issue.mentions} mentions</p>
                    </div>
                    <span className="text-sm font-medium text-gray-700">{Math.round(sliderValue * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={Math.round(sliderValue * 100)}
                    onChange={(event) => {
                      const nextValue = Number(event.target.value) / 100;
                      setFixes((current) => ({ ...current, [key]: clampToZeroToOne(nextValue) }));
                    }}
                    className="w-full accent-blue-600"
                    aria-label={`Fix impact for ${issue.aspect ?? 'other'}`}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="enterprise-card p-6">
          <h3 className="text-lg font-semibold mb-4">Projected average</h3>
          <div className="mb-4 rounded bg-[#eeefff] p-4">
            <p className="text-sm text-blue-700">Current avg</p>
            <p className="text-3xl font-bold text-blue-900">{currentAvg.toFixed(2)}</p>
          </div>
          <div className="mb-4 rounded bg-green-50 p-4">
            <p className="text-sm text-green-700">Projected avg</p>
            <p className="text-3xl font-bold text-green-900">{projectedAvg.toFixed(2)}</p>
          </div>
          <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
            <p className="font-semibold">Single-cause unhappy</p>
            <p className="mt-1">{simulation?.single_cause_unhappy_count ?? 0}</p>
          </div>
          {result.rating_source === 'pseudo' && (
            <div className="mt-3 inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">sentiment-based estimate</div>
          )}
        </div>
      </div>

      <div className="enterprise-card p-6">
        <h3 className="text-lg font-semibold mb-4">Before / after</h3>
        {loading && <p className="text-sm text-gray-500">Updating simulation...</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 5]} />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="enterprise-card p-6">
        <p className="text-sm text-gray-700">Estimates are associations from your review data, not guaranteed causes. Effects of several fixes are added; interactions are ignored.</p>
      </div>
    </div>
  );
};
