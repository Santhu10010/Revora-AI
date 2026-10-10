import React, { useState } from 'react';
import { Upload } from './components/Upload';
import { Overview } from './components/Overview';
import { DrillDown } from './components/DrillDown';
import { AnalyzeResponse } from './lib/api';
import './index.css';

type Page = 'upload' | 'overview' | 'drilldown';

function App() {
  const [page, setPage] = useState<Page>('upload');
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<{ aspect: string; polarity: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalysisComplete = (result: AnalyzeResponse) => {
    setResult(result);
    setPage('overview');
    setError(null);
  };

  const handleIssueClick = (aspect: string, polarity: string) => {
    setSelectedIssue({ aspect, polarity });
    setPage('drilldown');
  };

  const handleError = (error: string) => {
    setError(error);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Revora AI</h1>
          <p className="text-gray-600 text-sm mt-1">Product Review Insight Analyzer</p>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-4">
          <div className="max-w-6xl mx-auto">
            <p className="text-red-800">
              <span className="font-semibold">Error:</span> {error}
            </p>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-sm text-red-600 hover:text-red-800"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {page === 'upload' && (
          <Upload onAnalysisComplete={handleAnalysisComplete} onError={handleError} />
        )}

        {page === 'overview' && result && (
          <Overview result={result} onIssueClick={handleIssueClick} />
        )}

        {page === 'drilldown' && result && selectedIssue && (
          <DrillDown
            analysisId={result.analysis_id}
            aspect={selectedIssue.aspect}
            polarity={selectedIssue.polarity}
            onBack={() => setPage('overview')}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 mt-12 py-6 text-center text-sm text-gray-600">
        <p>Revora AI v0.1.0 • {result && `Mode: ${result.mode}`}</p>
      </footer>
    </div>
  );
}

export default App;
