import { useEffect, useId, useMemo, useRef, useState } from 'react';

/**
 * A checkbox dropdown: looks like the strip's other selects when closed, opens
 * to a tappable list of checkboxes. Nothing chosen means "all".
 *
 * `options` are plain strings (the readable value is also what is sent);
 * `value` is the array of chosen ones. A search box appears once the list is
 * long enough to need one.
 */
const SEARCH_FROM = 8;

export default function MultiSelect({ id, label, allLabel, noun, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const boxRef = useRef(null);
  const listId = useId();

  const chosen = useMemo(() => new Set(value), [value]);

  // Close on a tap outside or on Escape.
  useEffect(() => {
    if (!open) return undefined;
    function onPointer(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return needle ? options.filter((o) => o.toLowerCase().includes(needle)) : options;
  }, [options, search]);

  function toggle(option) {
    onChange(chosen.has(option) ? value.filter((v) => v !== option) : [...value, option]);
  }

  const summary =
    value.length === 0
      ? allLabel
      : value.length <= 2
        ? value.join(', ')
        : `${value.length} ${noun} selected`;

  return (
    <div className="msel" ref={boxRef}>
      <button
        type="button"
        id={id}
        className={`msel-btn${value.length ? ' has' : ''}`}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={`${label}: ${summary}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="msel-text">{summary}</span>
      </button>
      {open ? (
        <div className="msel-pop" id={listId} role="group" aria-label={label}>
          {options.length >= SEARCH_FROM ? (
            <input
              type="text"
              className="msel-search"
              placeholder={`Search ${noun}`}
              aria-label={`Search ${noun}`}
              autoComplete="off"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          ) : null}
          <div className="msel-list">
            {shown.length ? (
              shown.map((option) => (
                <label key={option} className="msel-opt">
                  <input type="checkbox" checked={chosen.has(option)} onChange={() => toggle(option)} />
                  <span>{option}</span>
                </label>
              ))
            ) : (
              <div className="msel-none">{options.length ? 'No match' : `No ${noun} available`}</div>
            )}
          </div>
          <div className="msel-foot">
            <button type="button" className="resetlink" onClick={() => onChange([])} disabled={!value.length}>
              Clear
            </button>
            <button type="button" className="btn primary" onClick={() => setOpen(false)}>
              Done
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
