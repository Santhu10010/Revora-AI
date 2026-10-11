import { lazy, Suspense, useEffect, useState } from 'react';
import { AnalyzeResponse, ModelStatus, api } from './lib/api';
import './index.css';

const Actions = lazy(() => import('./components/Actions').then((module) => ({ default: module.Actions })));
const DrillDown = lazy(() => import('./components/DrillDown').then((module) => ({ default: module.DrillDown })));
const History = lazy(() => import('./components/History').then((module) => ({ default: module.History })));
const Overview = lazy(() => import('./components/Overview').then((module) => ({ default: module.Overview })));
const Simulator = lazy(() => import('./components/Simulator').then((module) => ({ default: module.Simulator })));
const Upload = lazy(() => import('./components/Upload').then((module) => ({ default: module.Upload })));

type Page = 'upload' | 'overview' | 'drilldown' | 'simulator' | 'actions' | 'history';

function App() {
  const [page, setPage] = useState<Page>('upload');
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<{ aspect: string; polarity: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('revora-theme') === 'dark');

  useEffect(() => {
    api.modelStatus()
      .then(setModelStatus)
      .catch(() => setModelStatus(null));
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark-theme', darkMode);
    localStorage.setItem('revora-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const handleAnalysisComplete = (nextResult: AnalyzeResponse) => {
    setResult(nextResult);
    setPage('overview');
    setError(null);
  };

  const handleIssueClick = (aspect: string, polarity: string) => {
    setSelectedIssue({ aspect, polarity });
    setPage('drilldown');
  };

  const handleOpenAnalysis = async (analysisId: string) => {
    try {
      const nextResult = await api.getAnalysis(analysisId);
      setResult(nextResult);
      setPage('overview');
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load analysis';
      setError(message);
    }
  };

  const navItems: Array<{ key: Page; label: string; enabled: boolean }> = [
    { key: 'upload', label: 'Upload', enabled: true },
    { key: 'overview', label: 'Overview', enabled: Boolean(result) },
    { key: 'drilldown', label: 'DrillDown', enabled: Boolean(result && selectedIssue) },
    { key: 'simulator', label: 'Simulator', enabled: Boolean(result) },
    { key: 'actions', label: 'Actions', enabled: Boolean(result) },
    { key: 'history', label: 'History', enabled: true },
  ];

  return (
    <div className={`min-h-screen bg-[#f7f9fb] text-[#191c1e] ${darkMode ? 'dark-theme' : ''}`}>
      <header className="theme-header sticky top-0 z-40 border-b border-[#e0e3e5] bg-white">
        <div className="flex h-14 items-center justify-between gap-4 px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex shrink-0 items-center gap-2">
              <div className="brand-mark flex h-7 w-7 items-center justify-center rounded bg-[#111827] text-sm font-bold text-white">R</div>
              <div>
                <h1 className="text-sm font-semibold tracking-tight text-[#191c1e]">Revora AI</h1>
                <p className="hidden text-[10px] uppercase tracking-[0.12em] text-[#737686] sm:block">Review intelligence</p>
              </div>
            </div>
            <div className="dataset-context hidden items-center gap-2 rounded border border-[#e0e3e5] bg-[#f2f4f6] px-3 py-1.5 lg:flex">
                <span className="font-mono text-[11px] uppercase text-[#515f74]">Dataset:</span>
                <span className="max-w-56 truncate font-mono text-xs text-[#191c1e]">{result?.filename ?? 'No dataset selected'}</span>
                {result && <span className="text-xs text-[#737686]">({result.review_count.toLocaleString()} reviews)</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {modelStatus && (
              <span className="hidden text-xs text-[#737686] lg:inline" title={modelStatus.message}>
                {modelStatus.active ? modelStatus.model_name : 'Lite scorer'}
              </span>
            )}
            <span className="hidden text-xs text-[#515f74] lg:inline">Docs</span>
            <span className="hidden rounded border border-[#e0e3e5] bg-[#f2f4f6] px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-[#515f74] lg:inline">Production</span>
            <div className="theme-toggle" aria-label="Color theme">
              <button
                type="button"
                onClick={() => setDarkMode(false)}
                aria-pressed={!darkMode}
                className={!darkMode ? 'theme-option active' : 'theme-option'}
              >
                <span aria-hidden="true">☀</span>
                <span className="hidden sm:inline">Light</span>
              </button>
              <button
                type="button"
                onClick={() => setDarkMode(true)}
                aria-pressed={darkMode}
                className={darkMode ? 'theme-option active' : 'theme-option'}
              >
                <span aria-hidden="true">☾</span>
                <span className="hidden sm:inline">Dark</span>
              </button>
            </div>
          </div>
        </div>
        <div className="theme-nav border-t border-[#eceef0] bg-white px-4 md:px-6">
          <nav className="mx-auto flex max-w-7xl gap-5 overflow-x-auto" aria-label="Primary navigation">
            {navItems.map((item) => (
              <button
                key={item.key}
                type="button"
                disabled={!item.enabled}
                onClick={() => setPage(item.key)}
                className={`whitespace-nowrap border-b-2 px-1 py-3 text-xs font-medium transition ${
                  page === item.key
                    ? 'border-[#004ac6] text-[#004ac6]'
                    : 'border-transparent text-[#515f74] hover:border-[#b4c5ff] hover:text-[#191c1e]'
                } ${item.enabled ? '' : 'cursor-not-allowed opacity-40'}`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {error && (
        <div className="border-b border-red-200 bg-red-50 px-4 py-3">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
            <p className="text-sm text-red-800">
              <span className="font-semibold">Error:</span> {error}
            </p>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-xs font-medium text-red-700 hover:text-red-900"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <main className="app-main mx-auto max-w-[1440px] px-4 py-6 md:px-6">
        <Suspense fallback={<div className="enterprise-card p-8 text-sm text-[#737686]">Loading workspace...</div>}>
          {page === 'upload' && <Upload onAnalysisComplete={handleAnalysisComplete} onError={setError} />}
          {page === 'overview' && result && <Overview result={result} onIssueClick={handleIssueClick} />}
          {page === 'drilldown' && result && selectedIssue && (
            <DrillDown
              analysisId={result.analysis_id}
              aspect={selectedIssue.aspect}
              polarity={selectedIssue.polarity}
              onBack={() => setPage('overview')}
            />
          )}
          {page === 'simulator' && result && <Simulator result={result} />}
          {page === 'actions' && result && <Actions result={result} />}
          {page === 'history' && <History onOpen={handleOpenAnalysis} onUpload={() => setPage('upload')} />}
        </Suspense>
      </main>

      <footer className="theme-footer mt-12 border-t border-[#e0e3e5] bg-white px-6 py-5 text-xs text-[#737686]">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <p>Revora Engine v0.1.0{result ? ` · Mode: ${result.mode}` : ''}</p>
          <p className="font-mono"><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#b4c5ff]" /> All systems operational</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
