import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import api from '../api.js';
import { copyText, csvFilename, downloadCsv, toPlainText } from '../lib/exportList.js';
import SailingRow from './SailingRow.jsx';

/**
 * The finder — the main screen.
 *
 * Filtering and sorting are done by the server, not here. The share-by-email
 * and WhatsApp endpoints have to rebuild the same list to attach it to a PDF,
 * so the rules live in one place: app/routers/schedule.py. This component owns
 * the filter *state* and nothing else.
 *
 * Copy list and Download (CSV) act on exactly what is on screen.
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

/** Two or three mutually exclusive choices, shown as one control. */
function Segmented({ label, options, value, onChange }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? 'seg on' : 'seg'}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function Finder() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [routing, setRouting] = useState('all');
  const [mode, setMode] = useState('all');
  const [sort, setSort] = useState('etd');

  const [options, setOptions] = useState({ countries: [], ports: [], carriers: [] });
  const [sailings, setSailings] = useState([]);
  const [count, setCount] = useState(0);
  const [truncated, setTruncated] = useState(false);

  const [loading, setLoading] = useState(true);
  // Kept apart from "no sailings matched" on purpose: a failed fetch and an
  // empty result must never look the same.
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState('');

  const [customerView, setCustomerView] = useState(false);

  const noticeTimer = useRef(null);

  const flash = useCallback((message) => {
    setNotice(message);
    clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(''), 4000);
  }, []);

  useEffect(() => () => clearTimeout(noticeTimer.current), []);

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
        setCount(data.count);
        setTruncated(data.truncated);
        setLoadError('');
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setSailings([]);
        setCount(0);
        setLoadError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [query]);

  function setFilter(key, value) {
    setFilters((current) => {
      const next = { ...current, [key]: value };
      // Changing country invalidates the chosen port — it may not be in the
      // new country at all.
      if (key === 'country') next.pod_code = '';
      return next;
    });
  }

  function reset() {
    setFilters(EMPTY_FILTERS);
    setRouting('all');
    setMode('all');
    setSort('etd');
    flash('Filters reset.');
  }

  async function onCopy() {
    try {
      await copyText(toPlainText(sailings));
      flash(`Copied ${sailings.length} sailing${sailings.length === 1 ? '' : 's'}.`);
    } catch (err) {
      flash(err.message);
    }
  }

  function onDownload() {
    downloadCsv(sailings);
    flash(`Downloaded ${csvFilename()}.`);
  }

  async function onShare(kind) {
    // Both endpoints are stubbed until feature/share brings SMTP and Interakt
    // keys. The buttons are here and wired so the screen is complete; the
    // server says plainly that it cannot send yet.
    try {
      if (kind === 'email') {
        await api.shareEmail({ to: [], subject: '', note: '', filters: query });
      } else {
        await api.shareWhatsApp({ number: '', save: false, name: '', filters: query });
      }
    } catch (err) {
      flash(err.message);
    }
  }

  const hasSailings = sailings.length > 0;
  const internal = customerView ? 'internal hidden' : 'internal';

  return (
    <section className={customerView ? 'finder customer-view' : 'finder'}>
      <div className="filters">
        <div className="field">
          <label htmlFor="f-country">Country</label>
          <select
            id="f-country"
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

        <div className="field">
          <label htmlFor="f-port">Port</label>
          <select
            id="f-port"
            value={filters.pod_code}
            onChange={(e) => setFilter('pod_code', e.target.value)}
          >
            <option value="">{filters.country ? `All ports in ${filters.country}` : 'All ports'}</option>
            {options.ports.map((p) => (
              <option key={p.code} value={p.code}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="f-carrier">Carrier</label>
          <select
            id="f-carrier"
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

        <fieldset className="range">
          <legend>Departs between</legend>
          <input
            type="date"
            aria-label="Departs on or after"
            value={filters.etd_from}
            onChange={(e) => setFilter('etd_from', e.target.value)}
          />
          <span className="range-sep">and</span>
          <input
            type="date"
            aria-label="Departs on or before"
            value={filters.etd_to}
            onChange={(e) => setFilter('etd_to', e.target.value)}
          />
        </fieldset>

        <fieldset className="range">
          <legend>Arrives between</legend>
          <input
            type="date"
            aria-label="Arrives on or after"
            value={filters.eta_from}
            onChange={(e) => setFilter('eta_from', e.target.value)}
          />
          <span className="range-sep">and</span>
          <input
            type="date"
            aria-label="Arrives on or before"
            value={filters.eta_to}
            onChange={(e) => setFilter('eta_to', e.target.value)}
          />
        </fieldset>
      </div>

      <div className="toggles">
        <Segmented label="Routing" options={ROUTING} value={routing} onChange={setRouting} />
        <Segmented label="Which sailings" options={MODE} value={mode} onChange={setMode} />

        <div className="field sort">
          <label htmlFor="f-sort">Sort by</label>
          <select id="f-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="actions">
        <button type="button" onClick={reset}>
          Reset
        </button>
        <button type="button" className={internal} onClick={onCopy} disabled={!hasSailings}>
          Copy list
        </button>
        <button type="button" className={internal} onClick={onDownload} disabled={!hasSailings}>
          Download (CSV)
        </button>
        <button type="button" className={internal} onClick={() => onShare('whatsapp')} disabled={!hasSailings}>
          WhatsApp
        </button>
        <button type="button" className={internal} onClick={() => onShare('email')} disabled={!hasSailings}>
          Email these
        </button>

        {/* Not .internal — hiding this would leave no way back out of
            customer view. */}
        <label className="customer-toggle">
          <input
            type="checkbox"
            checked={customerView}
            onChange={(e) => setCustomerView(e.target.checked)}
          />
          Customer view
        </label>
      </div>

      {notice ? (
        <p className="notice" role="status">
          {notice}
        </p>
      ) : null}

      {loadError ? (
        <p className="error" role="alert">
          {loadError}
        </p>
      ) : null}

      <p className="result-count" aria-live="polite">
        {loading
          ? 'Loading sailings…'
          : loadError
            ? 'Could not load the schedule.'
            : `${count} sailing${count === 1 ? '' : 's'}`}
        {truncated ? ' (showing the first 2000 — narrow the filters)' : ''}
      </p>

      {!loading && !loadError && !hasSailings ? (
        <p className="empty">
          No sailings match these filters. Try widening the dates, or Reset.
        </p>
      ) : null}

      <ul className="sailings">
        {sailings.map((sailing) => (
          <SailingRow key={sailing.row_key} sailing={sailing} />
        ))}
      </ul>
    </section>
  );
}
