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
    } catch (err: any) {
      onError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <ScrollExpand className="bg-white rounded-lg shadow p-8">
        <h2 className="text-2xl font-bold mb-6">Upload Review Data</h2>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
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
              <div className="text-gray-600">
                {file ? (
                  <>
                    <p className="font-semibold text-lg">{file.name}</p>
                    <p className="text-sm mt-2">Click to change file</p>
                  </>
                ) : (
                  <>
                    <p className="text-lg mb-2">Drag and drop your CSV or XLSX file</p>
                    <p className="text-sm">or click to browse</p>
                  </>
                )}
              </div>
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Analysis Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'lite' | 'full')}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="lite">Lite (Fast, hosted)</option>
              <option value="full">Full (Accurate, local)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              {mode === 'lite'
                ? 'Fast lexicon-based analysis, no AI models'
                : 'Slower but more accurate with transformer models'}
            </p>
          </div>

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full bg-blue-600 text-white py-3 rounded-md font-semibold disabled:bg-gray-400 hover:bg-blue-700"
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </form>

        <div className="mt-6 p-4 bg-gray-50 rounded-md text-sm text-gray-600">
          <p className="font-semibold mb-2">Supported formats:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>CSV with columns: review_text, rating (optional), date (optional), version (optional)</li>
            <li>Excel (.xlsx) with the same columns</li>
            <li>Max 2,000 rows for Lite mode, 5,000 for Full mode</li>
            <li>Email addresses and phone numbers are redacted</li>
          </ul>
        </div>
      </ScrollExpand>
    </div>
  );
};
