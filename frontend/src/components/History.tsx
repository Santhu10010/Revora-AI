import { useEffect, useState } from 'react';
import { AnalysisListItem, api } from '../lib/api';

interface HistoryProps {
  onOpen: (analysisId: string) => void;
  onUpload: () => void;
}

export const History: React.FC<HistoryProps> = ({ onOpen, onUpload }) => {
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalyses = async () => {
    try {
      setLoading(true);
      setError(null);
      const payload = await api.listAnalyses();
      setAnalyses(payload.analyses);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load history';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalyses();
  }, []);

  const handleDelete = async (analysisId: string) => {
    const confirmed = window.confirm('Delete this analysis from memory?');
    if (!confirmed) {
      return;
    }

    try {
      await api.deleteAnalysis(analysisId);
      setAnalyses((current) => current.filter((analysis) => analysis.id !== analysisId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      setError(message);
    }
  };

  if (loading) {
    return <div className="enterprise-card mx-auto max-w-4xl p-8"><p className="text-[#737686]">Loading analysis history...</p></div>;
  }

  if (error) {
    return <div className="enterprise-card mx-auto max-w-4xl p-8"><p className="text-red-600">{error}</p><button type="button" onClick={loadAnalyses} className="mt-4 rounded bg-[#004ac6] px-3 py-2 text-sm font-medium text-white">Retry</button></div>;
  }

  if (analyses.length === 0) {
    return (
      <div className="enterprise-card mx-auto max-w-3xl p-10 text-center">
        <h2 className="mb-3 text-2xl font-semibold">No saved analyses</h2>
        <p className="mb-6 text-[#737686]">Upload a review file to create a saved analysis.</p>
        <button type="button" onClick={onUpload} className="rounded bg-[#004ac6] px-4 py-2 text-sm font-medium text-white hover:bg-[#003ea8]">Upload a review file</button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="enterprise-card p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Audit log</p>
            <h2 className="text-2xl font-semibold">Analysis history</h2>
            <p className="text-sm text-[#737686]">History is stored locally and remains available after backend restarts.</p>
          </div>
          <button type="button" onClick={onUpload} className="rounded border border-[#e0e3e5] px-3 py-2 text-sm font-medium text-[#515f74] hover:bg-[#f2f4f6]">Upload</button>
        </div>
      </div>

      <div className="enterprise-card overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-[#f2f4f6] text-[#515f74]">
            <tr>
              <th className="px-4 py-3 font-semibold">Date</th>
              <th className="px-4 py-3 font-semibold">Filename</th>
              <th className="px-4 py-3 font-semibold">Reviews</th>
              <th className="px-4 py-3 font-semibold">Mode</th>
              <th className="px-4 py-3 font-semibold">Avg rating</th>
              <th className="px-4 py-3 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {analyses.map((analysis) => (
              <tr key={analysis.id} className="border-t border-[#e0e3e5]">
                <td className="px-4 py-3 text-[#737686]">{new Date(analysis.created_at).toLocaleString()}</td>
                <td className="px-4 py-3 font-medium text-[#191c1e]">{analysis.filename}</td>
                <td className="px-4 py-3 text-[#515f74]">{analysis.review_count}</td>
                <td className="px-4 py-3 text-[#515f74]">{analysis.mode}</td>
                <td className="px-4 py-3 text-[#515f74]">{analysis.avg_rating !== null ? analysis.avg_rating.toFixed(2) : '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button type="button" onClick={() => onOpen(analysis.id)} className="rounded bg-[#004ac6] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[#003ea8]">Open</button>
                    <button type="button" onClick={() => handleDelete(analysis.id)} className="rounded border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50">Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
