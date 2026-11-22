// Root component: owns the screen state (input -> results -> detail), the latest analysis, and the anonymous user id.
import { useState } from 'react';
import Input from './components/Input.jsx';
import ProfilePanel from './components/ProfilePanel.jsx';
import Results from './components/Results.jsx';
import SchemeDetail from './components/SchemeDetail.jsx';
import Footer from './components/Footer.jsx';
import ErrorBanner from './components/ErrorBanner.jsx';
import { getUserId } from './api.js';

export default function App() {
  const [userId] = useState(getUserId);
  const [screen, setScreen] = useState('input');
  const [analysis, setAnalysis] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');

  function handleResult(res) {
    setError('');
    setAnalysis(res);
    setScreen('results');
  }

  function handleUpdate(res) {
    setError('');
    setAnalysis(res);
  }

  function openScheme(scheme) {
    setSelected(scheme);
    setScreen('detail');
  }

  function restart() {
    setError('');
    setAnalysis(null);
    setSelected(null);
    setScreen('input');
  }

  return (
    <div className="mx-auto max-w-3xl px-4 pb-8">
      <header className="mb-5 border-b-4 border-slate-900 py-5">
        <h1 className="text-3xl font-bold">Claim What's Yours</h1>
      </header>

      <ErrorBanner message={error} onClose={() => setError('')} />

      <main className="space-y-5">
        {screen === 'input' && <Input onResult={handleResult} onError={setError} />}

        {screen === 'results' && analysis && (
          <>
            <button
              type="button"
              className="min-h-[3rem] rounded border-2 border-slate-800 bg-white px-4 py-2 font-semibold"
              onClick={restart}
            >
              Start again
            </button>
            <ProfilePanel
              profile={analysis.profile}
              questions={analysis.questions || []}
              warnings={analysis.warnings || []}
              onUpdate={handleUpdate}
              onError={setError}
            />
            <Results data={analysis} onOpenScheme={openScheme} />
          </>
        )}

        {screen === 'detail' && selected && (
          <SchemeDetail
            scheme={selected}
            userId={userId}
            onBack={() => setScreen('results')}
          />
        )}
      </main>

      <Footer />
    </div>
  );
}
