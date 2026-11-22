// Free-text (or recorded voice) description form that sends the user's situation to /api/analyze.
import { useRef, useState } from 'react';
import { analyze, transcribe } from '../api.js';

const canRecord =
  typeof MediaRecorder !== 'undefined' && typeof navigator !== 'undefined' && !!navigator.mediaDevices;

export default function Describe({ onAnalyzed }) {
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('en');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await analyze(text, language);
      onAnalyzed(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        try {
          const res = await transcribe(blob);
          const spoken = typeof res === 'string' ? res : res.text || '';
          setText((prev) => (prev ? `${prev} ${spoken}` : spoken));
        } catch (err) {
          setError(err.message);
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="describe" onSubmit={handleSubmit}>
      <textarea
        className="describe-text"
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="I am 17, my father drives an auto, we earn about 1.8 lakh a year, I study in class 11 in a govt school."
      />
      <div className="describe-controls">
        <label>
          Language{' '}
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="hi">Hindi</option>
            <option value="te">Telugu</option>
          </select>
        </label>
        {canRecord && (
          <button type="button" onClick={toggleRecording}>
            {recording ? 'Stop recording' : 'Record voice'}
          </button>
        )}
        <button type="submit" disabled={busy || !text.trim()}>
          {busy ? 'Checking...' : 'Check my eligibility'}
        </button>
      </div>
      {error && <p className="message error" role="alert">{error}</p>}
    </form>
  );
}
