import { useEffect, useMemo, useState } from 'react';

import api from '../api.js';
import { copyText, downloadCsv, toPlainText } from '../lib/exportList.js';
import EnquiryModal from './EnquiryModal.jsx';
import SailingRow from './SailingRow.jsx';

/**
 * Find sailings — the #v-finder view of reference/Index.html.
 *
 * Markup and class names follow the reference one-for-one; app.css carries its
 * styles unchanged. Filtering and sorting are done by the server, not here:
 * the share-by-email and WhatsApp endpoints rebuild the same list to attach it
 * to a PDF, so the rules live in one place, app/routers/schedule.py. This
 * component owns the filter *state* and nothing else.
 *
 * Copy list and Download act on exactly what is on screen.
 */

const EMPTY_FILTERS = {
  country: '',
  pod_code: '',
  carrier: '',
  etd_from: '',
  etd_to: '',
  eta_from: '',
  eta_to: '',
};

const ROUTING = [
  { value: 'all', label: 'All' },
  { value: 'direct', label: 'Direct' },
  { value: 'indirect', label: 'Indirect' },
];

const MODE = [
  { value: 'all', label: 'All sailings' },
  { value: 'next_per_port', label: 'Next per port' },
];

const SORTS = [
  { value: 'etd', label: 'Soonest departure' },
  { value: 'transit', label: 'Fastest transit' },
  { value: 'eta', label: 'Soonest arrival' },
];

/** The reference's `.seg` group: two or three mutually exclusive choices. */
function Seg({ label, options, value, onChange }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function Finder({ flash }) {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [routing, setRouting] = useState('all');
  const [mode, setMode] = useState('all');
  const [sort, setSort] = useState('etd');

  const [options, setOptions] = useState({ countries: [], ports: [], carriers: [] });
  const [sailings, setSailings] = useState([]);
  const [count, setCount] = useState(null);
  const [truncated, setTruncated] = useState(false);

  // Kept apart from "no sailings matched" on purpose: a failed fetch and an
  // empty result must never look the same.
  const [loadError, setLoadError] = useState('');
  const [retry, setRetry] = useState(0);

  // Which share box is open under the action bar: '', 'email' or 'wa'.
  const [box, setBox] = useState('');
  const [mailTo, setMailTo] = useState('');
  const [mailToast, setMailToast] = useState('');
  const [waContacts, setWaContacts] = useState([]);
  const [waSelect, setWaSelect] = useState('');
  const [waManual, setWaManual] = useState('');
  const [waRemember, setWaRemember] = useState(false);
  const [waName, setWaName] = useState('');

  const [enquiring, setEnquiring] = useState(null);

  const query = useMemo(
    () => ({ ...filters, routing, mode, sort }),
    [filters, routing, mode, sort],
  );

  // --- dropdown options; ports cascade from the chosen country ---------------
  useEffect(() => {
    const controller = new AbortController();
    api
      .scheduleFilters(filters.country, controller.signal)
      .then(setOptions)
      .catch((err) => {
        if (err.name !== 'AbortError') setLoadError(err.message);
      });
    return () => controller.abort();
  }, [filters.country, retry]);

  // --- the list --------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();

    api
      .schedule(query, controller.signal)
      .then((data) => {
        setSailings(data.rows);
        setCount(data.count);
        setTruncated(data.truncated);
        setLoadError('');
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setSailings([]);
        setCount(null);
        setLoadError(err.message);
      });

    return () => controller.abort();
  }, [query, retry]);

  function setFilter(key, value) {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      // Changing country invalidates the chosen port — it may not be in the
      // new country at all.
      if (key === 'country') next.pod_code = '';
      return next;
    });
  }

  // Same scope as the reference's Reset: filters and Direct/Indirect. The
  // view and sort choices stay as they are.
  function reset() {
    setFilters(EMPTY_FILTERS);
    setRouting('all');
  }

  async function onCopy() {
    setBox('');
    try {
      await copyText(toPlainText(sailings));
      flash('Sailing list copied.');
    } catch {
      flash("Couldn't copy automatically.");
    }
  }

  function onDownload() {
    downloadCsv(sailings);
    flash('Downloaded — opens in Excel.');
  }

  function openWhatsApp() {
    setBox('wa');
    api
      .waContacts()
      .then((list) => setWaContacts(Array.isArray(list) ? list : []))
      .catch(() => setWaContacts([]));
  }

  async function sendMail() {
    const to = mailTo.trim();
    if (!to) {
      setMailToast('Enter an email address first.');
      return;
    }
    setMailToast('Sending…');
    try {
      await api.shareEmail({ to: [to], subject: '', note: '', filters: query });
      setMailToast(`Email sent to ${to}`);
    } catch (err) {
      setMailToast(`Could not send: ${err.message}`);
    }
  }

  async function sendWhatsApp() {
    const number = waManual.trim() || waSelect.trim();
    if (!number) {
      flash('Choose a saved number or type one.');
      return;
    }
    if (!sailings.length) {
      flash('No sailings to send — adjust the filters.');
      return;
    }
    flash('Sending PDF on WhatsApp…');
    try {
      await api.shareWhatsApp({
        number,
        save: Boolean(waManual.trim()) && waRemember,
        name: waName.trim(),
        filters: query,
      });
      flash(`Sent to ${number}`);
      setBox('');
    } catch (err) {
      flash(`Could not send: ${err.message}`);
    }
  }

  const portLabel = filters.country ? `All ports in ${filters.country}` : 'All ports';

  return (
    <div className="view active" id="v-finder">
      <div className="wrap">
        <div className="panel">
          <div className="row">
            <div className="control">
              <label className="lbl" htmlFor="country">Country</label>
              <select id="country" value={filters.country} onChange={(e) => setFilter('country', e.target.value)}>
                <option value="">All countries</option>
                {options.countries.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="control">
              <label className="lbl" htmlFor="dest">Port</label>
              <select id="dest" value={filters.pod_code} onChange={(e) => setFilter('pod_code', e.target.value)}>
                <option value="">{portLabel}</option>
                {options.ports.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="control">
              <label className="lbl" htmlFor="car">Carrier</label>
              <select id="car" value={filters.carrier} onChange={(e) => setFilter('carrier', e.target.value)}>
                <option value="">All carriers</option>
                {options.carriers.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="row">
            <div className="control dates">
              <label className="lbl">Departs between</label>
              <div className="pair">
                <input type="date" aria-label="Departs from" value={filters.etd_from} onChange={(e) => setFilter('etd_from', e.target.value)} />
                <span>to</span>
                <input type="date" aria-label="Departs to" value={filters.etd_to} onChange={(e) => setFilter('etd_to', e.target.value)} />
              </div>
            </div>
            <div className="control dates">
              <label className="lbl">Arrives between</label>
              <div className="pair">
                <input type="date" aria-label="Arrives from" value={filters.eta_from} onChange={(e) => setFilter('eta_from', e.target.value)} />
                <span>to</span>
                <input type="date" aria-label="Arrives to" value={filters.eta_to} onChange={(e) => setFilter('eta_to', e.target.value)} />
              </div>
            </div>
          </div>
        </div>

        <div className="bar">
          <div className="count" aria-live="polite">
            {count === null ? (
              '—'
            ) : (
              <>
                <b>{count}</b> sailing{count === 1 ? '' : 's'}
                {mode === 'next_per_port' ? ' (next per port)' : ''}
                {truncated ? ' (first 2000 — narrow the filters)' : ''}
              </>
            )}
          </div>
          <div className="spacer" />
          <Seg label="Shipment type" options={ROUTING} value={routing} onChange={setRouting} />
          <Seg label="View" options={MODE} value={mode} onChange={setMode} />
          <select className="minisort" aria-label="Sort by" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="actions internal">
          <button type="button" className="btn ghost" onClick={reset}>
            Reset
          </button>
          <div className="spacer" />
          <button type="button" className="btn" onClick={onCopy}>
            Copy list
          </button>
          <button type="button" className="btn" onClick={onDownload}>
            Download
          </button>
          <button type="button" className="btn wa" onClick={openWhatsApp}>
            WhatsApp
          </button>
          <button type="button" className="btn primary" onClick={() => setBox('email')}>
            Email these
          </button>
        </div>

        {box === 'email' ? (
          <div className="mailbox internal">
            <h4>Email these sailings</h4>
            <div className="mailrow">
              <div className="control">
                <label className="lbl" htmlFor="to">Send to</label>
                <input type="email" id="to" placeholder="name@company.com" autoComplete="off" autoFocus value={mailTo} onChange={(e) => setMailTo(e.target.value)} />
              </div>
              <button type="button" className="btn primary" onClick={sendMail}>
                Send email
              </button>
              <a className="btn" href={api.sharePdfUrl(query)} target="_blank" rel="noopener noreferrer">
                Preview PDF
              </a>
              <button type="button" className="btn ghost" onClick={() => setBox('')}>
                Close
              </button>
            </div>
            <div className="toast" role="status">{mailToast}</div>
            <div className="hint">Send emails the sailing list directly from our account — one click, no email app.</div>
          </div>
        ) : null}

        {box === 'wa' ? (
          <div className="mailbox internal">
            <h4>Send these sailings on WhatsApp (PDF)</h4>
            <div className="mailrow">
              <div className="control">
                <label className="lbl" htmlFor="waSelect">Saved numbers</label>
                <select
                  id="waSelect"
                  value={waSelect}
                  onChange={(e) => {
                    setWaSelect(e.target.value);
                    if (e.target.value) setWaManual('');
                  }}
                >
                  <option value="">— choose a saved number —</option>
                  {waContacts.map((c) => (
                    <option key={c.number} value={c.number}>
                      {c.name ? `${c.name} — ` : ''}
                      {c.number}
                    </option>
                  ))}
                </select>
              </div>
              <div className="control">
                <label className="lbl" htmlFor="waManual">Or type a new number</label>
                <input type="tel" id="waManual" placeholder="98672 00083" autoComplete="off" autoFocus value={waManual} onChange={(e) => setWaManual(e.target.value)} />
              </div>
            </div>
            {waManual.trim() ? (
              <div className="mailrow">
                <label className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6, textTransform: 'none', fontSize: 13 }}>
                  <input type="checkbox" style={{ width: 'auto', height: 'auto' }} checked={waRemember} onChange={(e) => setWaRemember(e.target.checked)} /> Remember this number
                </label>
                <div className="control">
                  <input type="text" placeholder="Name / label (optional)" autoComplete="off" value={waName} onChange={(e) => setWaName(e.target.value)} />
                </div>
              </div>
            ) : null}
            <div className="mailrow">
              <button type="button" className="btn primary" onClick={sendWhatsApp}>
                Send PDF on WhatsApp
              </button>
              <a className="btn" href={api.sharePdfUrl(query)} target="_blank" rel="noopener noreferrer">
                Preview PDF
              </a>
              <button type="button" className="btn ghost" onClick={() => setBox('')}>
                Close
              </button>
            </div>
            <div className="hint">Applies the filters above, makes a PDF of those sailings, and sends it to the WhatsApp number with a short note.</div>
          </div>
        ) : null}

        <div className="list">
          {loadError ? (
            <div className="empty failed" role="alert">
              <h3>Couldn&apos;t load sailings</h3>
              <div>{loadError}</div>
              <button type="button" className="btn" onClick={() => setRetry((n) => n + 1)}>
                Try again
              </button>
            </div>
          ) : count !== null && sailings.length === 0 ? (
            <div className="empty">
              <h3>No sailings match</h3>
              <div>Try a different country, port, carrier or date range.</div>
            </div>
          ) : (
            sailings.map((sailing) => <SailingRow key={sailing.row_key} sailing={sailing} onEnquire={setEnquiring} />)
          )}
        </div>
        <div className="foot">Carrier estimates — confirm cut-offs before booking.</div>
      </div>

      {enquiring ? <EnquiryModal sailing={enquiring} onClose={() => setEnquiring(null)} flash={flash} /> : null}
    </div>
  );
}
