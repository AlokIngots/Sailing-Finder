import { useCallback, useEffect, useState } from 'react';

import api from '../api.js';

/**
 * Rate summary — every enquiry emailed from the Enquire modal, newest first,
 * with one column per forwarder and a box for the rate each one quoted.
 *
 * Not in reference/Index.html; built from its patterns (.bkhead, .panel,
 * .empty, table.q, .btn) so it sits in the same shell without changing it.
 *
 * Who sees which enquiries is decided on the server (services/enquiries.py):
 * a normal user gets their own, an admin everyone's. Nothing is filtered here.
 *
 * The rate is free text ("USD 1450 all-in") and is never checked or
 * reformatted — it saves as typed when the box loses focus or Enter is pressed.
 * A cell for a forwarder the enquiry was not sent to shows a dash.
 */
export default function Rates({ flash, isAdmin }) {
  const [rows, setRows] = useState(null);
  const [loadError, setLoadError] = useState('');

  const load = useCallback((signal) => {
    setLoadError('');
    return api
      .enquiries(signal)
      .then(setRows)
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setLoadError(err.message);
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  let body = null;
  if (loadError) {
    body = (
      <div className="empty failed" role="alert" style={{ marginTop: 10 }}>
        <h3>Couldn&apos;t load enquiries</h3>
        <div>{loadError}</div>
        <button type="button" className="btn" onClick={() => load()}>
          Try again
        </button>
      </div>
    );
  } else if (!rows) {
    body = (
      <p className="boot" role="status">
        Loading…
      </p>
    );
  } else if (!rows.length) {
    body = (
      <div className="empty" style={{ marginTop: 10 }}>
        <h3>No enquiries yet</h3>
        <div>Pick a sailing on Find sailings and press Enquire — it will appear here with its number.</div>
      </div>
    );
  } else {
    // Columns: every forwarder any listed enquiry went to, in first-seen order.
    const forwarders = [];
    for (const row of rows) {
      for (const q of row.quotes) {
        if (!forwarders.includes(q.forwarder_name)) forwarders.push(q.forwarder_name);
      }
    }

    body = (
      <div className="panel ratewrap">
        <table className="q rates">
          <thead>
            <tr>
              <th scope="col">Enquiry</th>
              {forwarders.map((name) => (
                <th scope="col" key={name}>
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const byName = Object.fromEntries(row.quotes.map((q) => [q.forwarder_name, q]));
              return (
                <tr key={row.ref}>
                  <th scope="row" className="enq">
                    <div className="ref">{row.ref}</div>
                    <div className="rt">{formatWhen(row.created_at)}</div>
                    <div className="rt">
                      {row.origin} → {row.pod_name}
                      {row.country ? `, ${row.country}` : ''}
                    </div>
                    {row.carrier || row.vessel ? (
                      <div className="rt">{[row.carrier, row.vessel].filter(Boolean).join(' · ')}</div>
                    ) : null}
                    <div className="rt">Sent to {row.quotes.map((q) => q.forwarder_name).join(', ') || '—'}</div>
                    {isAdmin ? <div className="rt">By {row.created_by}</div> : null}
                  </th>
                  {forwarders.map((name) =>
                    byName[name] ? (
                      <td key={name}>
                        {/* Names the cell when the table stacks on a phone. */}
                        <div className="mlbl">{name}</div>
                        <RateCell enquiryRef={row.ref} quote={byName[name]} forwarder={name} flash={flash} />
                      </td>
                    ) : (
                      <td key={name} className="na" aria-label={`Not sent to ${name}`}>
                        —
                      </td>
                    ),
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="view active" id="v-rates">
      <div className="wrap">
        <div className="bkhead">
          <h2>Rate summary</h2>
          <p>{isAdmin ? 'All enquiries' : 'Your enquiries'}, newest first. Type each forwarder&apos;s rate as they quote it.</p>
        </div>
        {body}
      </div>
    </div>
  );
}

/** One editable rate. Saves on blur or Enter, only when it changed. */
function RateCell({ enquiryRef, quote, forwarder, flash }) {
  const [value, setValue] = useState(quote.quoted_rate || '');
  const [savedValue, setSavedValue] = useState(quote.quoted_rate || '');
  const [state, setState] = useState(''); // '' | 'saving' | 'saved' | 'error'

  async function save() {
    if (value === savedValue || state === 'saving') return;
    setState('saving');
    try {
      await api.saveRate(enquiryRef, quote.id, value);
      setSavedValue(value);
      setState('saved');
    } catch (err) {
      setState('error');
      flash(`Could not save ${forwarder}'s rate for ${enquiryRef}: ${err.message}`);
    }
  }

  return (
    <div className={`ratecell ${state}`}>
      <input
        type="text"
        value={value}
        maxLength={100}
        placeholder="Rate"
        aria-label={`${forwarder} rate for ${enquiryRef}`}
        onChange={(e) => {
          setValue(e.target.value);
          if (state !== 'saving') setState('');
        }}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
      />
      <span className="st" aria-live="polite">
        {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved' : state === 'error' ? 'Not saved' : ''}
      </span>
    </div>
  );
}

function formatWhen(iso) {
  if (!iso) return '';
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return '';
  return when.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
