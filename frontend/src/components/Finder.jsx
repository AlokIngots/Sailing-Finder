import { useEffect, useMemo, useState } from 'react';

import api from '../api.js';
import { buildCsv, buildText, copyText, csvFilename, downloadCsv } from '../lib/exportList.js';
import flash from '../lib/flash.js';
import { fmt, tidy, whereLabel } from '../lib/format.js';
import SailingRow from './SailingRow.jsx';

/**
 * The finder — a port of the reference's `#v-finder`: the filter panel, the
 * count/segments/sort bar, the action row, the Email and WhatsApp boxes, and
 * the list.
 *
 * Filtering and sorting are done by the server, not here — the share endpoints
 * have to rebuild the same list to attach it to a PDF, so the rules live in
 * app/routers/schedule.py. This component owns the filter *state* and the
 * screen, nothing else.
 *
 * Customer view is not handled here either: App.jsx puts `customer` on <body>
 * and the reference's `body.customer .internal{display:none}` does the work,
 * exactly as in the original.
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

const TYPES = [
  { value: 'all', label: 'All' },
  { value: 'direct', label: 'Direct' },
  { value: 'indirect', label: 'Indirect' },
];

const VIEWS = [
  { value: 'all', label: 'All sailings' },
  { value: 'next_per_port', label: 'Next per port' },
];

export default function Finder() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [routing, setRouting] = useState('all');
  const [mode, setMode] = useState('all');
  const [sort, setSort] = useState('etd');

  const [options, setOptions] = useState({ countries: [], ports: [], carriers: [] });
  const [sailings, setSailings] = useState([]);
  const [loading, setLoading] = useState(true);
  // Kept apart from "no sailings matched" on purpose: a failed fetch and an
  // empty result must never look the same.
  const [loadError, setLoadError] = useState('');

  // Which of the two boxes is open. The reference shows at most one.
  const [box, setBox] = useState(null); // null | 'email' | 'whatsapp'
  const [emailTo, setEmailTo] = useState('');
  const [toast, setToast] = useState('');

  const [waContacts, setWaContacts] = useState([]);
  const [waContactsNote, setWaContactsNote] = useState('');
  const [waSaved, setWaSaved] = useState('');
  const [waManual, setWaManual] = useState('');
  const [waRemember, setWaRemember] = useState(false);
  const [waName, setWaName] = useState('');

  const [enquiry, setEnquiry] = useState(null);

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
  }, [filters.country]);

  // --- the list --------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    api
      .schedule(query, controller.signal)
      .then((data) => {
        setSailings(data.rows);
        setLoadError('');
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setSailings([]);
        setLoadError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [query]);

  const where = whereLabel({ podCode: filters.pod_code, country: filters.country, rows: sailings });

  function setFilter(key, value) {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      // Changing country invalidates the chosen port — it may not be in the new
      // country at all. The reference rebuilds the port <select>, which loses
      // the selection the same way.
      if (key === 'country') next.pod_code = '';
      return next;
    });
  }

  /** The reference's Reset: filters and type only. Sort and view stay put. */
  function reset() {
    setFilters(EMPTY_FILTERS);
    setRouting('all');
  }

  async function onCopy() {
    setBox(null);
    const { body } = buildText(sailings, where);
    flash((await copyText(body)) ? 'Sailing list copied.' : "Couldn't copy automatically.");
  }

  async function onDownload() {
    const csv = buildCsv(sailings);
    if (downloadCsv(csv, csvFilename())) {
      flash('Downloaded — opens in Excel.');
      return;
    }
    await copyText(csv);
    flash("Couldn't download — CSV copied instead.");
  }

  function openEmail() {
    setBox('email');
    setToast('');
  }

  function openWhatsApp() {
    setBox('whatsapp');
    if (!waContacts.length && !waContactsNote) loadWaContacts();
  }

  function loadWaContacts() {
    api
      .waContacts()
      .then((list) => setWaContacts(list || []))
      .catch((err) => {
        // The endpoint is a stub until feature/share. Say so in the dropdown
        // rather than leaving it looking empty-but-fine.
        setWaContactsNote(err.status === 501 ? 'saved numbers not available yet' : err.message);
      });
  }

  // Both share endpoints are stubbed until feature/share brings the SMTP and
  // Interakt keys. The buttons are live so the screen is complete; the server
  // says plainly that it cannot send.
  async function sendEmail() {
    const to = emailTo.trim();
    if (!to) {
      setToast('Enter an email address first.');
      return;
    }
    setToast('Sending…');
    const { subject } = buildText(sailings, where);
    try {
      await api.shareEmail({ to: [to], subject, note: '', filters: query });
      setToast(`Email sent to ${to}`);
    } catch (err) {
      setToast(`Could not send: ${err.message}`);
    }
  }

  async function sendWhatsApp() {
    const number = waManual.trim() || waSaved.trim();
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
      setBox(null);
    } catch (err) {
      flash(`Could not send: ${err.message}`);
    }
  }

  const count = sailings.length;

  return (
    <div className="view active" id="v-finder">
      <div className="wrap">
        <div className="panel">
          <div className="row">
            <div className="control">
              <label className="lbl" htmlFor="country">
                Country
              </label>
              <select
                id="country"
                value={filters.country}
                onChange={(e) => setFilter('country', e.target.value)}
              >
                <option value="">All countries</option>
                {options.countries.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="control">
              <label className="lbl" htmlFor="dest">
                Port
              </label>
              <select
                id="dest"
                value={filters.pod_code}
                onChange={(e) => setFilter('pod_code', e.target.value)}
              >
                <option value="">
                  {filters.country ? `All ports in ${filters.country}` : 'All ports'}
                </option>
                {options.ports.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="control">
              <label className="lbl" htmlFor="car">
                Carrier
              </label>
              <select
                id="car"
                value={filters.carrier}
                onChange={(e) => setFilter('carrier', e.target.value)}
              >
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
                <input
                  type="date"
                  id="dfrom"
                  aria-label="Departs from"
                  value={filters.etd_from}
                  onChange={(e) => setFilter('etd_from', e.target.value)}
                />
                <span>to</span>
                <input
                  type="date"
                  id="dto"
                  aria-label="Departs to"
                  value={filters.etd_to}
                  onChange={(e) => setFilter('etd_to', e.target.value)}
                />
              </div>
            </div>

            <div className="control dates">
              <label className="lbl">Arrives between</label>
              <div className="pair">
                <input
                  type="date"
                  id="afrom"
                  aria-label="Arrives from"
                  value={filters.eta_from}
                  onChange={(e) => setFilter('eta_from', e.target.value)}
                />
                <span>to</span>
                <input
                  type="date"
                  id="ato"
                  aria-label="Arrives to"
                  value={filters.eta_to}
                  onChange={(e) => setFilter('eta_to', e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="bar">
          <div className="count" id="count" aria-live="polite">
            {loading || loadError ? (
              '—'
            ) : (
              <>
                <b>{count}</b> sailing{count === 1 ? '' : 's'}
                {mode === 'next_per_port' ? ' (next per port)' : ''}
              </>
            )}
          </div>
          <div className="spacer" />

          <div className="seg" id="typeSeg" role="group" aria-label="Shipment type">
            {TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                aria-pressed={routing === t.value}
                onClick={() => setRouting(t.value)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="seg" id="viewSeg" role="group" aria-label="View">
            {VIEWS.map((v) => (
              <button
                key={v.value}
                type="button"
                aria-pressed={mode === v.value}
                onClick={() => setMode(v.value)}
              >
                {v.label}
              </button>
            ))}
          </div>

          <select
            id="sort"
            className="minisort"
            aria-label="Sort by"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="etd">Soonest departure</option>
            <option value="transit">Fastest transit</option>
            <option value="eta">Soonest arrival</option>
          </select>
        </div>

        <div className="actions internal">
          <button type="button" className="btn ghost" id="reset" onClick={reset}>
            Reset
          </button>
          <div className="spacer" />
          <button type="button" className="btn" id="copyBtn" onClick={onCopy}>
            Copy list
          </button>
          <button type="button" className="btn" id="dlBtn" onClick={onDownload}>
            Download
          </button>
          <button type="button" className="btn wa" id="waBtn" onClick={openWhatsApp}>
            WhatsApp
          </button>
          <button type="button" className="btn primary" id="emailBtn" onClick={openEmail}>
            Email these
          </button>
        </div>

        {box === 'email' ? (
          <div className="mailbox internal" id="mailbox">
            <h4>Email these sailings</h4>
            <div className="mailrow">
              <div className="control">
                <label className="lbl" htmlFor="to">
                  Send to
                </label>
                <input
                  type="email"
                  id="to"
                  placeholder="name@company.com"
                  autoComplete="off"
                  value={emailTo}
                  onChange={(e) => setEmailTo(e.target.value)}
                />
              </div>
              <button type="button" className="btn primary" id="sendMail" onClick={sendEmail}>
                Send email
              </button>
              <button type="button" className="btn ghost" id="closeMail" onClick={() => setBox(null)}>
                Close
              </button>
            </div>
            <div className="toast" id="toast">
              {toast}
            </div>
            <div className="hint">
              Send emails the sailing list directly from your Google account — one click, no email
              app.
            </div>
          </div>
        ) : null}

        {box === 'whatsapp' ? (
          <div className="mailbox internal" id="wabox">
            <h4>Send these sailings on WhatsApp (PDF)</h4>
            <div className="mailrow">
              <div className="control">
                <label className="lbl" htmlFor="waSelect">
                  Saved numbers
                </label>
                <select
                  id="waSelect"
                  value={waSaved}
                  onChange={(e) => {
                    setWaSaved(e.target.value);
                    if (e.target.value) {
                      setWaManual('');
                      setWaRemember(false);
                    }
                  }}
                >
                  <option value="">
                    {waContactsNote ? `— ${waContactsNote} —` : '— choose a saved number —'}
                  </option>
                  {waContacts.map((c) => (
                    <option key={c.number} value={c.number}>
                      {c.name ? `${c.name} — ${c.number}` : c.number}
                    </option>
                  ))}
                </select>
              </div>
              <div className="control">
                <label className="lbl" htmlFor="waManual">
                  Or type a new number
                </label>
                <input
                  type="tel"
                  id="waManual"
                  placeholder="98672 00083"
                  autoComplete="off"
                  value={waManual}
                  onChange={(e) => setWaManual(e.target.value)}
                />
              </div>
            </div>

            {waManual.trim() ? (
              <div className="mailrow" id="waRememberRow">
                <label
                  className="lbl"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    textTransform: 'none',
                    fontSize: '13px',
                  }}
                >
                  <input
                    type="checkbox"
                    id="waRemember"
                    style={{ width: 'auto', height: 'auto' }}
                    checked={waRemember}
                    onChange={(e) => setWaRemember(e.target.checked)}
                  />{' '}
                  Remember this number
                </label>
                <div className="control">
                  <input
                    type="text"
                    id="waName"
                    placeholder="Name / label (optional)"
                    autoComplete="off"
                    value={waName}
                    onChange={(e) => setWaName(e.target.value)}
                  />
                </div>
              </div>
            ) : null}

            <div className="mailrow">
              <button type="button" className="btn primary" id="waSend" onClick={sendWhatsApp}>
                Send PDF on WhatsApp
              </button>
              <button type="button" className="btn ghost" id="waClose" onClick={() => setBox(null)}>
                Close
              </button>
            </div>
            <div className="hint">
              Applies the filters above, makes a PDF of those sailings, and sends it to the WhatsApp
              number with a short note.
            </div>
          </div>
        ) : null}

        <div className="list" id="list">
          {loadError ? (
            <div className="empty">
              <h3>Couldn&rsquo;t load the schedule</h3>
              <div>{loadError}</div>
            </div>
          ) : loading ? null : count === 0 ? (
            <div className="empty">
              <h3>No sailings match</h3>
              <div>Try a different country, port, carrier or date range.</div>
            </div>
          ) : (
            sailings.map((sailing) => (
              <SailingRow key={sailing.row_key} sailing={sailing} onEnquire={setEnquiry} />
            ))
          )}
        </div>

        <div className="foot" id="foot">
          Carrier estimates — confirm cut-offs before booking.
        </div>
      </div>

      {/* Placeholder until feature/enquiry builds the form. The shell, the
          summary and the wording are the reference's. */}
      <div className={enquiry ? 'modal-bg show' : 'modal-bg'} id="bookModal">
        {enquiry ? (
          <div className="modal">
            <h3>Enquire about this sailing</h3>
            <p className="msub">
              Fill the details, review the email, then send it to your forwarders.
            </p>
            <div className="bk-summary">
              <b>{tidy(enquiry).vessel}</b>
              {tidy(enquiry).voyage ? ` (${tidy(enquiry).voyage})` : ''} — {enquiry.carrier}
              <br />
              {enquiry.pol_name || 'Nhava Sheva'} → {enquiry.pod_name || enquiry.pod_code},{' '}
              {enquiry.country}
              <br />
              Departs {fmt(enquiry.etd)} · Arrives {fmt(enquiry.eta)}
              {enquiry.transit_days != null ? ` · ${enquiry.transit_days} days` : ''}
            </div>
            <p className="msub">
              The enquiry form and sending to forwarders arrive on the next branch.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setEnquiry(null)}>
                Close
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
