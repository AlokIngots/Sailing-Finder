import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import api from '../api.js';
import { formatShort } from '../lib/format.js';

/**
 * My bookings — #v-bookings of reference/Index.html. Newest first, each with
 * a status chip: Request sent / Quotes in / Booked / Docs sent.
 *
 * The list is whatever api.bookings() returns; the server decides what this
 * user may see (their own, or everything for an admin). No filtering happens
 * here — a client-side filter would not be a security boundary.
 */

const CHIP = {
  sent: ['sent', 'Request sent'],
  quotes: ['quotes', 'Quotes in'],
  booked: ['booked', 'Booked'],
  docs: ['docs', 'Docs sent'],
};

export default function Bookings() {
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    api
      .bookings(controller.signal)
      .then((list) => setRows(Array.isArray(list) ? list : []))
      .catch((err) => {
        if (err.name !== 'AbortError') setLoadError(err.message);
      });
    return () => controller.abort();
  }, []);

  let body = null;
  if (loadError) {
    body = (
      <div className="empty failed" role="alert" style={{ marginTop: 10 }}>
        <h3>Couldn&apos;t load bookings</h3>
        <div>{loadError}</div>
      </div>
    );
  } else if (rows && !rows.length) {
    body = (
      <div className="empty" style={{ marginTop: 10 }}>
        <h3>No bookings yet</h3>
        <div>Send an enquiry from Find sailings and it shows up here.</div>
      </div>
    );
  } else if (rows) {
    body = rows.map((s) => {
      const [cls, label] = CHIP[s.stage] || CHIP.sent;
      return (
        <div
          key={s.ref}
          className="brow"
          role="link"
          tabIndex={0}
          onClick={() => navigate(`/bookings/${encodeURIComponent(s.ref)}`)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate(`/bookings/${encodeURIComponent(s.ref)}`);
          }}
        >
          <div className="bl">
            <div className="ref">{s.ref}</div>
            <div className="ves">
              {s.vessel} · {s.carrier}
            </div>
            <div className="rt">
              Nhava Sheva → {s.pod_name || s.pod_code}
              {s.country ? `, ${s.country}` : ''} · ETD {formatShort(s.etd)}
            </div>
          </div>
          <span className={`chip ${cls}`}>{label}</span>
          <span className="chevron">›</span>
        </div>
      );
    });
  }

  return (
    <div className="view active" id="v-bookings">
      <div className="wrap">
        <div className="bkhead">
          <h2>My bookings</h2>
          <p>Every shipment you&apos;ve booked and where it stands.</p>
        </div>
        <div>{body}</div>
        <div className="foot">Newest first · click a shipment to work its steps.</div>
      </div>
    </div>
  );
}
