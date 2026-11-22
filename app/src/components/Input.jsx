// Input screen: language choice, free-text or voice description of the user's situation, and sample profiles.
import { useState } from 'react';
import { analyze, transcribe } from '../api.js';

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'te', label: 'తెలుగు (Telugu)' },
  { value: 'hi', label: 'हिंदी (Hindi)' },
];

const SAMPLES = [
  {
    label: 'English sample',
    language: 'en',
    text: 'I am a 17 year old student studying in class 11 in Andhra Pradesh, our family income is about 1.8 lakh a year',
  },
  {
    label: 'Telugu sample',
    language: 'te',
    text: 'నేను ఆంధ్రప్రదేశ్ లో 17 ఏళ్ల విద్యార్థిని, మా కుటుంబ వార్షిక ఆదాయం 1.8 లక్షలు',
  },
];

const VOICE_SUPPORTED =
  typeof MediaRecorder !== 'undefined' &&
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices;

export default function Input({ onResult, onError }) {
  const [language, setLanguage] = useState('en');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState(null);

  async function runAnalyze(value, lang) {
    setBusy(true);
    try {
      const res = await analyze(value, lang);
      onResult(res);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function handleCheck(e) {
    e.preventDefault();
    if (!text.trim()) {
      onError('Please describe your situation first.');
      return;
    }
    runAnalyze(text, language);
  }

  async function sendAudio(blob) {
    setBusy(true);
    try {
      const res = await transcribe(blob, language);
      const transcript = res.transcript ?? res.text ?? '';
      setText(transcript);
      if (!transcript.trim()) {
        onError('We could not hear anything. Please try again or type your situation.');
        return;
      }
      const analysis = await analyze(transcript, language);
      onResult(analysis);
    } catch (err) {
      if (err.status === 501) {
        onError('Voice input is not set up yet. Please type your situation.');
      } else {
        onError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunks.push(ev.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
        sendAudio(blob);
      };
      rec.start();
      setRecorder(rec);
      setRecording(true);
    } catch (err) {
      onError('Microphone access was not allowed. Please type your situation.');
    }
  }

  function stopRecording() {
    if (recorder) recorder.stop();
    setRecorder(null);
    setRecording(false);
  }

  return (
    <section className="rounded-lg border-2 border-slate-800 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-2xl font-bold">Describe your situation</h2>

      <label htmlFor="language" className="mt-2 block font-semibold">Language</label>
      <select
        id="language"
        className="mb-4 w-full rounded border-2 border-slate-700 p-2"
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
      >
        {LANGUAGES.map((l) => (
          <option key={l.value} value={l.value}>{l.label}</option>
        ))}
      </select>

      <label htmlFor="situation" className="block font-semibold">Tell us about yourself</label>
      <textarea
        id="situation"
        className="mb-3 min-h-[9rem] w-full rounded border-2 border-slate-700 p-3"
        placeholder="I am 17, my father drives an auto, we earn about 1.8 lakh a year, I study in class 11 in a govt school."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <p className="mb-3 rounded bg-amber-50 p-3 text-base font-semibold text-slate-800">
        Do not enter Aadhaar, PAN, or bank details.
      </p>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="min-h-[3rem] rounded bg-blue-800 px-5 py-2 font-bold text-white disabled:opacity-50"
          onClick={handleCheck}
          disabled={busy}
        >
          {busy ? 'Checking...' : 'Check schemes'}
        </button>
        {VOICE_SUPPORTED && (
          <button
            type="button"
            className={`min-h-[3rem] rounded border-2 px-5 py-2 font-bold disabled:opacity-50 ${
              recording ? 'border-red-700 bg-red-700 text-white' : 'border-slate-800 bg-white'
            }`}
            onClick={recording ? stopRecording : startRecording}
            disabled={busy}
            aria-pressed={recording}
          >
            {recording ? 'Stop recording' : 'Speak instead'}
          </button>
        )}
      </div>

      <h3 className="mb-2 mt-4 text-lg font-semibold">Try a sample profile</h3>
      <div className="flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s.label}
            type="button"
            className="min-h-[3rem] rounded border-2 border-slate-800 bg-white px-4 py-2 font-semibold"
            onClick={() => {
              setLanguage(s.language);
              setText(s.text);
            }}
          >
            {s.label}
          </button>
        ))}
      </div>
    </section>
  );
}
