// Results: disclaimer, selection note, scheme cards with verdict badges and reasons, and a collapsed "Not matching" list.

const BADGE = {
  likely_eligible: { label: 'Likely eligible', cls: 'bg-green-700 text-white' },
  possibly_eligible: { label: 'Needs verification', cls: 'bg-amber-500 text-slate-900' },
  needs_verification: { label: 'Needs verification', cls: 'bg-amber-500 text-slate-900' },
  not_eligible: { label: 'Likely ineligible', cls: 'bg-slate-500 text-white' },
};

const REASON = {
  PASS: { label: '[PASS] Met', cls: 'bg-green-100 border-green-700' },
  UNVERIFIED: { label: '[UNVERIFIED] Needs checking', cls: 'bg-yellow-100 border-yellow-600' },
  FAIL: { label: '[FAIL] Not met', cls: 'bg-red-100 border-red-700' },
};

function ResultCard({ scheme, onOpenScheme }) {
  const badge = BADGE[scheme.verdict] || BADGE.needs_verification;
  const reasons = scheme.reasons || [];
  const unresolved = scheme.unresolved_conditions || [];

  return (
    <article className="rounded-lg border-2 border-slate-800 bg-white p-5">
      <h3 className="text-xl font-bold">{scheme.name}</h3>
      <span className={`mb-2 inline-block rounded px-3 py-1 font-bold ${badge.cls}`}>{badge.label}</span>
      <p className="mb-2">{scheme.benefit}</p>

      <ul className="mb-3 space-y-2">
        {reasons.map((r, i) => {
          const tag = REASON[r.result] || { label: r.result, cls: 'bg-slate-100 border-slate-500' };
          return (
            <li key={i} className={`rounded border-l-4 p-2 ${tag.cls}`}>
              <span className="font-bold">{tag.label}</span> {r.text}
              {r.explanation && <p className="text-base text-slate-700">{r.explanation}</p>}
            </li>
          );
        })}
      </ul>

      {unresolved.length > 0 && (
        <div className="mb-3 rounded border-2 border-amber-600 bg-amber-50 p-3">
          <p className="font-semibold">Confirm this condition on the official portal</p>
          <ul className="list-disc pl-6">
            {unresolved.map((c, i) => (
              <li key={i}>{String(c)}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="mb-1 text-base text-slate-700">
        Last verified: {scheme.last_verified || 'not recorded'}
      </p>
      {scheme.official_source && (
        <p className="mb-3">
          <a className="font-semibold text-blue-800 underline" href={scheme.official_source} target="_blank" rel="noreferrer">
            Official link
          </a>
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="min-h-[3rem] rounded border-2 border-slate-800 bg-white px-4 py-2 font-semibold"
          onClick={() => onOpenScheme(scheme)}
        >
          Show documents and steps
        </button>
      </div>
    </article>
  );
}

export default function Results({ data, onOpenScheme }) {
  const results = data.results || [];
  const notMatching = data.not_matching || [];

  return (
    <section className="space-y-4">
      <p className="rounded border-2 border-slate-800 bg-slate-100 p-4 font-semibold">
        This shows likely eligibility based on public information. It is not a guarantee. Confirm on the official portal.
      </p>

      {data.selection_note && <p className="rounded bg-blue-50 p-3">{data.selection_note}</p>}

      {results.length === 0 && <p className="font-semibold">No matching schemes found yet. Try adding more details.</p>}

      {results.map((scheme) => (
        <ResultCard key={scheme.scheme_id} scheme={scheme} onOpenScheme={onOpenScheme} />
      ))}

      {notMatching.length > 0 && (
        <details className="rounded-lg border-2 border-slate-800 bg-white p-4">
          <summary className="cursor-pointer font-bold">Not matching ({notMatching.length})</summary>
          <ul className="mt-3 space-y-3">
            {notMatching.map((s) => (
              <li key={s.scheme_id}>
                <p className="font-semibold">{s.name}</p>
                <ul className="list-disc pl-6 text-base text-slate-700">
                  {(s.reasons || []).map((r, i) => (
                    <li key={i}>
                      {typeof r === 'string' ? r : r.explanation || r.text || ''}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
