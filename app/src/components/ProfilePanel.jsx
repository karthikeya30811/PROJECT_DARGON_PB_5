// Profile panel: shows the detected profile as chips, lets the user edit fields, and answers follow-up questions.
import { useState } from 'react';
import { answers } from '../api.js';

// Option values must match the backend's CHOICE_FIELDS exactly (engine/match.py).
const CHOICE = {
  state: ['Andhra Pradesh'],
  category: ['SC', 'ST', 'BC', 'OC', 'EWS', 'MINORITY'],
  education_level: ['primary', 'secondary', 'intermediate', 'graduate', 'postgraduate'],
  occupation: ['student', 'farmer', 'daily_wage', 'auto_driver', 'self_employed', 'salaried', 'unemployed', 'homemaker', 'retired', 'other'],
  gender: ['female', 'male', 'other'],
};

// Readable label for a backend value, e.g. 'daily_wage' -> 'Daily wage'. The stored value stays the backend value.
function optionLabel(value) {
  const text = value.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const FIELDS = [
  { key: 'state', label: 'State', kind: 'choice' },
  { key: 'category', label: 'Category', kind: 'choice' },
  { key: 'annual_family_income', label: 'Annual family income (Rs)', kind: 'number' },
  { key: 'education_level', label: 'Education level', kind: 'choice' },
  { key: 'occupation', label: 'Occupation', kind: 'choice' },
  { key: 'age', label: 'Age', kind: 'number' },
  { key: 'land_acres', label: 'Land (acres)', kind: 'number' },
  { key: 'has_bank_account', label: 'Has bank account', kind: 'bool' },
  { key: 'has_ration_card', label: 'Has ration card', kind: 'bool' },
  { key: 'has_disability', label: 'Has disability', kind: 'bool' },
];

function displayValue(field, value) {
  if (value === null || value === undefined || value === '') return 'Not known yet';
  if (field.kind === 'bool') return value ? 'Yes' : 'No';
  return String(value);
}

function parseValue(kind, raw) {
  if (kind === 'number') return raw === '' ? null : Number(raw);
  if (kind === 'bool') return raw === 'yes';
  return raw;
}

function choicesFor(field, options) {
  return options && options.length ? options : CHOICE[field] || [];
}

function FieldInput({ kind, value, options, onChange, id }) {
  const common = 'w-full rounded border-2 border-slate-700 p-2';
  if (kind === 'number') {
    return (
      <input
        id={id}
        type="number"
        className={common}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (kind === 'bool') {
    return (
      <select id={id} className={common} value={value === true ? 'yes' : value === false ? 'no' : ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    );
  }
  return (
    <select id={id} className={common} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select</option>
      {options.map((o) => (
        <option key={o} value={o}>{optionLabel(o)}</option>
      ))}
    </select>
  );
}

export default function ProfilePanel({ profile, questions = [], warnings = [], onUpdate, onError }) {
  const [edited, setEdited] = useState({});
  const [collected, setCollected] = useState({});
  const [busy, setBusy] = useState(false);

  async function submit(payload) {
    setBusy(true);
    try {
      const res = await answers(profile, payload);
      onUpdate(res);
      setEdited({});
      setCollected({});
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const p = profile || {};

  return (
    <section className="space-y-4">
      <div className="rounded-lg border-2 border-slate-800 bg-white p-5">
        <h2 className="mb-3 text-2xl font-bold">What we understood</h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {FIELDS.map((f) => (
            <span key={f.key} className="rounded-full border-2 border-slate-700 px-3 py-1 text-base">
              <strong>{f.label}:</strong> {displayValue(f, p[f.key])}
            </span>
          ))}
        </div>

        <h3 className="mb-2 text-lg font-semibold">Correct anything here</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label htmlFor={`edit-${f.key}`} className="block font-semibold">{f.label}</label>
              <FieldInput
                id={`edit-${f.key}`}
                kind={f.kind}
                value={f.key in edited ? edited[f.key] : p[f.key]}
                options={choicesFor(f.key, null)}
                onChange={(raw) =>
                  setEdited({ ...edited, [f.key]: parseValue(f.kind, raw) })
                }
              />
            </div>
          ))}
        </div>
        <button
          type="button"
          className="mt-4 min-h-[3rem] w-full rounded bg-blue-800 px-5 py-2 font-bold text-white disabled:opacity-50"
          disabled={busy || Object.keys(edited).length === 0}
          onClick={() => submit(edited)}
        >
          Update results
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="rounded-lg border-2 border-amber-600 bg-amber-50 p-4">
          <h3 className="mb-2 font-semibold">Please note</h3>
          <ul className="list-disc pl-6">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {questions.length > 0 && (
        <div className="rounded-lg border-2 border-slate-800 bg-white p-5">
          <h2 className="mb-3 text-2xl font-bold">A few quick questions</h2>
          <div className="space-y-4">
            {questions.map((q) => (
              <div key={q.field}>
                <p className="mb-2 font-semibold">{q.question}</p>
                {q.kind === 'bool' ? (
                  <div className="flex gap-2">
                    {[{ v: true, l: 'Yes' }, { v: false, l: 'No' }].map((o) => (
                      <button
                        key={o.l}
                        type="button"
                        aria-pressed={collected[q.field] === o.v}
                        className={`min-h-[3rem] rounded border-2 px-5 py-2 font-bold ${
                          collected[q.field] === o.v
                            ? 'border-blue-800 bg-blue-800 text-white'
                            : 'border-slate-800 bg-white'
                        }`}
                        onClick={() => setCollected({ ...collected, [q.field]: o.v })}
                      >
                        {o.l}
                      </button>
                    ))}
                  </div>
                ) : (
                  <FieldInput
                    id={`q-${q.field}`}
                    kind={q.kind}
                    value={collected[q.field]}
                    options={choicesFor(q.field, q.options)}
                    onChange={(raw) =>
                      setCollected({ ...collected, [q.field]: parseValue(q.kind, raw) })
                    }
                  />
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            className="mt-4 min-h-[3rem] w-full rounded bg-blue-800 px-5 py-2 font-bold text-white disabled:opacity-50"
            disabled={busy || Object.keys(collected).length === 0}
            onClick={() => submit(collected)}
          >
            Update results
          </button>
        </div>
      )}
    </section>
  );
}
