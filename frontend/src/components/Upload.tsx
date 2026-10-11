import React, { useState } from 'react';
import { api, AnalyzeResponse } from '../lib/api';
import { ScrollExpand } from './ScrollExpand';

interface UploadProps {
  onAnalysisComplete: (result: AnalyzeResponse) => void;
  onError: (error: string) => void;
}

export const Upload: React.FC<UploadProps> = ({ onAnalysisComplete, onError }) => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'lite' | 'full'>('lite');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      onError('Please select a file');
      return;
    }

    setLoading(true);
    try {
      const result = await api.analyze(file, mode);
      onAnalysisComplete(result);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1440px]">
      <div className="mb-8 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#737686]">Import & review ingestion</p>
          <h2 className="text-3xl font-semibold tracking-tight text-[#191c1e]">Upload review data</h2>
          <p className="mt-2 text-sm text-[#515f74]">Map your review corpus into a traceable product intelligence report.</p>
        </div>
        <span className="rounded bg-[#f2f4f6] px-2 py-1 font-mono text-xs text-[#515f74]">INGESTION PIPELINE V2.4</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.8fr)]">
        <ScrollExpand className="enterprise-card p-6 md:p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Source file selection</h3>
              <span className="font-mono text-xs text-[#737686]">CSV / XLSX</span>
            </div>
            <div className="rounded border border-dashed border-[#b4c5ff] bg-[#f7f9fb] p-10 text-center transition hover:border-[#004ac6] hover:bg-[#f2f4f6]">
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              disabled={loading}
              className="hidden"
              id="file-input"
            />
            <label
              htmlFor="file-input"
              className="cursor-pointer block"
            >
              <div className="text-[#515f74]">
                {file ? (
                  <>
                    <p className="font-mono text-sm font-semibold text-[#191c1e]">{file.name}</p>
                    <p className="mt-2 text-xs">Click to change file</p>
                  </>
                ) : (
                  <>
                    <p className="mb-2 text-base font-medium text-[#191c1e]">Drop your CSV or XLSX file here</p>
                    <p className="text-xs">or click to browse from your device</p>
                  </>
                )}
              </div>
            </label>
            </div>

            {file && (
              <div className="flex items-center justify-between gap-3 rounded bg-[#f2f4f6] p-3 text-sm">
                <div><p className="font-mono font-semibold">{file.name}</p><p className="text-xs text-[#737686]">Validated for ingestion</p></div>
                <span className="rounded bg-green-50 px-2 py-1 text-xs font-semibold text-green-700">READY</span>
              </div>
            )}

            <div>
              <div className="mb-3 flex items-center justify-between">
                <label className="block text-xs font-semibold uppercase tracking-wide text-[#515f74]">Analysis mode & clustering depth</label>
                <span className="text-xs text-[#737686]">Select pipeline configuration</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {(['lite', 'full'] as const).map((option) => (
                  <label key={option} className={`cursor-pointer rounded border p-4 ${mode === option ? 'border-[#004ac6] bg-[#f7f9fb]' : 'border-[#e0e3e5]'}`}>
                    <input type="radio" name="mode" value={option} checked={mode === option} onChange={() => setMode(option)} className="mr-2 accent-blue-600" />
                    <span className="font-semibold">{option === 'lite' ? 'Lite mode' : 'Full mode'}</span>
                    <p className="mt-2 text-xs leading-relaxed text-[#515f74]">{option === 'lite' ? 'Fast keyword and sentiment extraction for exploratory scans.' : 'Deep issue clustering and rating impact association.'}</p>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-[#e0e3e5] pt-5">
              <span className="text-xs text-[#515f74]">Estimated execution time: <span className="font-mono">~{mode === 'lite' ? '15' : '90'} seconds</span></span>
              <button type="submit" disabled={!file || loading} className="rounded bg-[#004ac6] px-6 py-3 font-semibold text-white transition hover:bg-[#003ea8] disabled:cursor-not-allowed disabled:bg-[#c3c6d7]">
                {loading ? 'Analyzing...' : `Start analysis (${mode === 'full' ? 'full' : 'lite'} mode)`}
              </button>
            </div>
          </form>

        </ScrollExpand>

        <aside className="space-y-6">
          <div className="enterprise-card p-6">
            <h3 className="mb-4 text-lg font-semibold">Pre-flight validation</h3>
            {['File format recognized', 'Required review text field', 'PII redaction enabled', 'Duplicate detection enabled'].map((item) => (
              <div key={item} className="mb-2 rounded bg-[#f2f4f6] p-3 text-sm"><span className="mr-2 text-[#004ac6]">✓</span>{item}</div>
            ))}
          </div>
          <div className="enterprise-card p-6 text-xs text-[#515f74]">
            <h3 className="mb-3 text-lg font-semibold text-[#191c1e]">Input contract</h3>
            <ul className="list-inside list-disc space-y-2">
              <li>CSV or Excel with review_text and optional rating, date, version</li>
              <li>Maximum 2,000 rows for Lite and 5,000 for Full</li>
              <li>Email addresses and phone numbers are redacted</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
};
