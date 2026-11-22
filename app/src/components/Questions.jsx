// Asks the follow-up questions one at a time and submits the collected answers to /api/answers.
import { useState } from 'react';
import { answers } from '../api.js';

// Questions without a kind are treated as yes/no; otherwise only kind "bool" gets Yes/No.
function isBoolQuestion(q) {
  return q.kind === undefined ? true : q.kind === 'bool';
}

export default function Questions({ questions, profile, onDone }) {
  const [index, setIndex] = useState(0);
  const [collected, setCollected] = useState({});
  const [value, setValue] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const total = questions.length;
  const q = questions[index];

  async function finish(finalAnswers) {
    setBusy(true);
    setError('');
    try {
      const res = await answers(profile, finalAnswers);
      onDone(res);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  function advance(nextAnswers) {
    setCollected(nextAnswers);
    if (index + 1 < total) {
      setIndex(index + 1);
      setValue('');
    } else {
      finish(nextAnswers);
    }
  }

  function answerWith(val) {
    advance({ ...collected, [q.field]: val });
  }

  if (total === 0 || !q) {
    return (
      <div className="questions">
        <p>No questions to answer.</p>
        <button type="button" onClick={() => finish(collected)} disabled={busy}>
          Continue
        </button>
        {error && <p className="message error" role="alert">{error}</p>}
      </div>
    );
  }

  const prompt = q.question || q.text || q.label || q.field;

  return (
    <div className="questions">
      <h2>Question {index + 1} of {total}</h2>
      <p>{prompt}</p>
      {isBoolQuestion(q) ? (
        <div className="question-actions">
          <button type="button" onClick={() => answerWith(true)} disabled={busy}>Yes</button>
          <button type="button" onClick={() => answerWith(false)} disabled={busy}>No</button>
          <button type="button" onClick={() => advance(collected)} disabled={busy}>Skip</button>
        </div>
      ) : (
        <form
          className="question-actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (value === '') return;
            answerWith(Number(value));
          }}
        >
          <input
            type="number"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={busy}
          />
          <button type="submit" disabled={busy || value === ''}>Next</button>
          <button type="button" onClick={() => advance(collected)} disabled={busy}>Skip</button>
        </form>
      )}
      {error && <p className="message error" role="alert">{error}</p>}
    </div>
  );
}
