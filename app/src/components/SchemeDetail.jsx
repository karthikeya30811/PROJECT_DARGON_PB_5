// Scheme detail: documents checklist, numbered steps, where to apply, deadline, tracker form and reminders.
import { useEffect, useState } from 'react';
import { getTracker, icsUrl, saveTracker } from '../api.js';

const STATUSES = ['Not Started', 'Documents Ready', 'Applied', 'Follow-up Due', 'Completed'];

export default function SchemeDetail({ scheme, userId, onBack }) {
  const checklist = scheme.checklist || {};
  const documents = checklist.documents || [];
  const steps = checklist.steps || scheme.steps || [];

  const [checked, setChecked] = useState({});
  const [status, setStatus] = useState(STATUSES[0]);
  const [applicationId, setApplicationId] = useState('');
  const [appliedOn, setAppliedOn] = useState('');
  const [saveMsg, setSaveMsg] = useState('');
  const [error, setError] = useState('');
  const [reminders, setReminders] = useState([]);

  useEffect(() => {
    let cancelled = false;
    getTracker(userId)
      .then((res) => {
        if (!cancelled) setReminders(res.reminders || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function handleSave(e) {
    e.preventDefault();
    setSaveMsg('');
    setError('');
    try {
      await saveTracker({
        user_id: userId,
        scheme_id: scheme.scheme_id,
        status,
        application_id: applicationId,
        applied_on: appliedOn,
      });
      setSaveMsg('Saved.');
    } catch (err) {
      setError(err.message);
    }
  }

  const deadline = scheme.deadline || scheme.deadline_date;

  return (
    <section className="space-y-4">
      <button
        type="button"
        className="min-h-[3rem] rounded border-2 border-slate-800 bg-white px-4 py-2 font-semibold"
        onClick={onBack}
      >
        Back
      </button>

      <div className="rounded-lg border-2 border-slate-800 bg-white p-5">
        <h2 className="mb-2 text-2xl font-bold">{scheme.name}</h2>
        <p className="mb-4">{scheme.benefit}</p>

        <h3 className="mb-2 text-lg font-semibold">Documents</h3>
        {documents.length === 0 && <p className="text-base text-slate-700">No document list recorded.</p>}
        <ul className="mb-4 space-y-2">
          {documents.map((doc, i) => (
            <li key={i}>
              <label className="flex items-start gap-3 font-normal">
                <input
                  type="checkbox"
                  className="mt-1 h-5 w-5"
                  checked={!!checked[i]}
                  onChange={(e) => setChecked({ ...checked, [i]: e.target.checked })}
                />
                <span>{doc.label}</span>
              </label>
            </li>
          ))}
        </ul>

        <h3 className="mb-2 text-lg font-semibold">Steps</h3>
        <ol className="mb-4 list-decimal space-y-1 pl-6">
          {steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>

        {checklist.where_to_apply != null && (
          <p className="mb-2"><strong>Where to apply:</strong> {checklist.where_to_apply}</p>
        )}
        {checklist.terms_and_conditions != null && (
          <p className="mb-2"><strong>Terms and conditions:</strong> {checklist.terms_and_conditions}</p>
        )}
        <p className="mb-4">
          <strong>Deadline:</strong> {deadline ? deadline : 'No deadline recorded'}
        </p>
      </div>

      <div className="rounded-lg border-2 border-slate-800 bg-white p-5">
        <h3 className="mb-3 text-lg font-semibold">Track your application</h3>
        <form className="space-y-3" onSubmit={handleSave}>
          <div>
            <label htmlFor="status" className="block font-semibold">Status</label>
            <select
              id="status"
              className="w-full rounded border-2 border-slate-700 p-2"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="app-id" className="block font-semibold">Application ID</label>
            <input
              id="app-id"
              type="text"
              className="w-full rounded border-2 border-slate-700 p-2"
              value={applicationId}
              onChange={(e) => setApplicationId(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="applied-on" className="block font-semibold">Applied on</label>
            <input
              id="applied-on"
              type="date"
              className="w-full rounded border-2 border-slate-700 p-2"
              value={appliedOn}
              onChange={(e) => setAppliedOn(e.target.value)}
            />
          </div>
          <button type="submit" className="min-h-[3rem] w-full rounded bg-blue-800 px-5 py-2 font-bold text-white">
            Save
          </button>
          {saveMsg && <p className="font-semibold text-green-800">{saveMsg}</p>}
        </form>
        <p className="mt-4">
          <a className="font-semibold text-blue-800 underline" href={icsUrl(userId)}>
            Download calendar reminder (.ics)
          </a>
        </p>
      </div>

      <div className="rounded-lg border-2 border-slate-800 bg-white p-5">
        <h3 className="mb-2 text-lg font-semibold">Reminders</h3>
        {reminders.length === 0 && <p className="text-base text-slate-700">No reminders yet.</p>}
        <ul className="list-disc space-y-1 pl-6">
          {reminders.map((r, i) => (
            <li key={i}>
              {r.message} {r.due_date && <span>({r.due_date})</span>}
            </li>
          ))}
        </ul>
      </div>

      {error && <p className="font-semibold text-red-700" role="alert">{error}</p>}
    </section>
  );
}
