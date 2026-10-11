import { useEffect, useMemo, useState } from 'react';
import { ActionResponse, AnalyzeResponse, api } from '../lib/api';

interface ActionsProps {
  result: AnalyzeResponse;
}

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

export const Actions: React.FC<ActionsProps> = ({ result }) => {
  const issueOptions = useMemo(() => result.top_issues.slice(0, 5), [result.top_issues]);
  const [selectedIssue, setSelectedIssue] = useState<string>(issueOptions[0]?.aspect ?? 'other');
  const [selectedPolarity, setSelectedPolarity] = useState<string>(issueOptions[0]?.polarity ?? 'neg');
  const [action, setAction] = useState<ActionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (issueOptions.length === 0) {
      setAction(null);
      return;
    }
    const firstIssue = issueOptions[0];
    setSelectedIssue(firstIssue.aspect ?? 'other');
    setSelectedPolarity(firstIssue.polarity);
  }, [issueOptions]);

  useEffect(() => {
    if (issueOptions.length === 0 || !selectedIssue) {
      return;
    }

    const loadAction = async () => {
      try {
        setLoading(true);
        setError(null);
        const nextAction = await api.generateActions(result.analysis_id, selectedIssue, selectedPolarity);
        setAction(nextAction);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to generate action plan';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    loadAction();
  }, [result.analysis_id, selectedIssue, selectedPolarity, issueOptions]);

  const handleExport = async (format: 'csv' | 'md' | 'markdown') => {
    try {
      const blob = await api.exportAnalysis(result.analysis_id, format);
      const extension = format === 'csv' ? 'csv' : 'md';
      downloadBlob(blob, `analysis-${result.analysis_id}.${extension}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to export file';
      setError(message);
    }
  };

  const copyToClipboard = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setError(`${label} copied to clipboard.`);
    } catch {
      setError('Clipboard access is unavailable in this browser.');
    }
  };

  if (issueOptions.length === 0) {
    return (
      <div className="enterprise-card mx-auto max-w-3xl p-8">
        <h2 className="mb-4 text-2xl font-semibold">Actions</h2>
        <p className="text-[#737686]">No issue data is available to generate actions.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="enterprise-card p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Response operations</p>
            <h2 className="text-2xl font-semibold">Actions & response drafting</h2>
            <p className="text-sm text-[#737686]">Generate ticket drafts and export issue reports.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => handleExport('csv')} className="rounded bg-[#004ac6] px-3 py-2 text-sm font-medium text-white hover:bg-[#003ea8]">Export CSV</button>
            <button type="button" onClick={() => handleExport('md')} className="rounded border border-[#e0e3e5] px-3 py-2 text-sm font-medium text-[#515f74] hover:bg-[#f2f4f6]">Export Markdown</button>
          </div>
        </div>
      </div>

      <div className="enterprise-card p-6">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
          <label className="text-sm font-medium text-gray-700">Issue</label>
          <select
            value={`${selectedIssue}:${selectedPolarity}`}
            onChange={(event) => {
              const [aspect, polarity] = event.target.value.split(':');
              setSelectedIssue(aspect);
              setSelectedPolarity(polarity);
            }}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {issueOptions.map((issue) => (
              <option key={`${issue.aspect}:${issue.polarity}`} value={`${issue.aspect ?? 'other'}:${issue.polarity}`}>
                {issue.aspect ?? 'Other'} ({issue.polarity})
              </option>
            ))}
          </select>
        </div>

        {loading && <p className="text-sm text-gray-600">Generating action draft...</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {action && (
          <div className="space-y-6">
            <div className="rounded-md border border-blue-100 bg-blue-50 p-4">
              <div className="mb-2 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-blue-700">Ticket</p>
                  <h3 className="text-xl font-bold text-blue-900">{action.title}</h3>
                </div>
                <div className="flex gap-2">
                  <span className="rounded-full bg-gray-900 px-2 py-1 text-xs font-semibold text-white">{action.team}</span>
                  <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-800">{action.priority}</span>
                </div>
              </div>
              <p className="text-sm text-gray-700">{action.summary}</p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-md border border-gray-200 p-4">
                <h4 className="font-semibold mb-2">Next steps</h4>
                <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                  {action.next_steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-md border border-gray-200 p-4">
                <h4 className="font-semibold mb-2">Success metric</h4>
                <p className="text-sm text-gray-700">{action.success_metric}</p>
                <p className="mt-3 text-sm text-gray-700">Estimated uplift: +{action.estimated_rating_uplift.toFixed(2)} rating points</p>
              </div>
            </div>

            <div className="rounded-md border border-gray-200 p-4">
              <h4 className="font-semibold mb-3">Evidence</h4>
              <ol className="space-y-2">
                {action.evidence.map((item) => (
                  <li key={`${item.review_id}-${item.text.slice(0, 20)}`} className="rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                    <span className="font-semibold text-gray-900">{item.review_id}</span> — “{item.text}”
                  </li>
                ))}
              </ol>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-md border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="font-semibold">English draft</h4>
                  <button type="button" onClick={() => copyToClipboard(action.reply_drafts.english, 'English draft')} className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500">Copy</button>
                </div>
                <pre className="whitespace-pre-wrap text-sm text-gray-700">{action.reply_drafts.english}</pre>
              </div>
              <div className="rounded-md border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="font-semibold">Hinglish draft</h4>
                  <button type="button" onClick={() => copyToClipboard(action.reply_drafts.hinglish, 'Hinglish draft')} className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500">Copy</button>
                </div>
                <pre className="whitespace-pre-wrap text-sm text-gray-700">{action.reply_drafts.hinglish}</pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
