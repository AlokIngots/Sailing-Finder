import { useEffect, useState } from 'react';

import api from '../api.js';
import { formatDate, tidyVessel } from '../lib/format.js';

/**
 * The enquiry modal — #bookModal of reference/Index.html: details -> Review
 * request -> Send to forwarders.
 *
 * Fields: stuffing date, containers, net/gross weight, commodity,
 * target-rate/remarks. These are operator-judgement fields — free text, no
 * "that looks wrong" validation.
 *
 * The review pane shows the email the request is built from. It is read-only:
 * POST /api/enquiry sends the fields, and the server writes and sends the
 * email to each forwarder separately, so edits made here would never arrive.
 */

const COMMODITY = 'Stainless steel bright bars';

function buildEmail(sailing, fields) {
  const { vessel, voyage } = tidyVessel(sailing);
  const port = sailing.pod_name || sailing.pod_code;
  const where = `${port}${sailing.country ? `, ${sailing.country}` : ''}`;
  const transit = Number.isFinite(sailing.transit_days) ? sailing.transit_days : null;

  const subject = `Booking request — Nhava Sheva to ${where} (${sailing.carrier} ${vessel})`;
  const L = [];
  L.push('We would like to book the shipment below. Please send your best all-in rate and the latest booking cut-off for this vessel.');
  L.push('');
  L.push(`Carrier: ${sailing.carrier}`);
  L.push(`Vessel / voyage: ${vessel}${voyage ? ` / ${voyage}` : ''}`);
  L.push('From: Nhava Sheva (INNSA)');
  L.push(`To: ${where}${sailing.pod_code ? ` (${sailing.pod_code})` : ''}`);
  L.push(`ETD: ${formatDate(sailing.etd) || '—'}   ETA: ${formatDate(sailing.eta) || '—'}${transit !== null ? `   Transit: ${transit} days` : ''}`);
  if (fields.stuffing) L.push(`Stuffing date: ${fields.stuffing}`);
  if (fields.container) L.push(`Containers: ${fields.container}`);
  if (fields.commodity) L.push(`Commodity: ${fields.commodity}`);
  if (fields.net_wt || fields.gross_wt) {
    L.push(`Weight: ${fields.net_wt || '—'} net${fields.gross_wt ? ` / ${fields.gross_wt} gross` : ''}`);
  }
  if (fields.remarks) L.push(`Remarks: ${fields.remarks}`);
  L.push('');
  L.push('Please confirm space and quote by return.');
  L.push('');
  L.push('Warm regards,');
  L.push('Export Team');
  L.push('Alok Ingots (Mumbai) Pvt. Ltd.');
  return { subject, body: L.join('\n') };
}

function Recipients({ forwarders }) {
  if (!forwarders.length) return <div className="recips">No forwarders are set up yet.</div>;
  return (
    <div className="recips">
      Will be emailed to:{' '}
      {forwarders.map((f, i) => (
        <span key={f.id || f.name}>
          {i ? ', ' : ''}
          <b>{f.name}</b>
        </span>
      ))}
    </div>
  );
}

export default function EnquiryModal({ sailing, onClose, flash }) {
  const [fields, setFields] = useState({
    stuffing: '',
    container: '',
    net_wt: '',
    gross_wt: '',
    commodity: COMMODITY,
    remarks: '',
  });
  const [reviewing, setReviewing] = useState(false);
  const [forwarders, setForwarders] = useState([]);
  const [toast, setToast] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api
      .forwarders()
      .then((list) => setForwarders(Array.isArray(list) ? list : []))
      .catch(() => setForwarders([]));
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const set = (key) => (e) => setFields((f) => ({ ...f, [key]: e.target.value }));

  const { vessel, voyage } = tidyVessel(sailing);
  const port = sailing.pod_name || sailing.pod_code;
  const transit = Number.isFinite(sailing.transit_days) ? ` · ${sailing.transit_days} days` : '';
  const email = reviewing ? buildEmail(sailing, fields) : null;

  async function send() {
    setToast('Sending…');
    setSending(true);
    try {
      await api.enquiry({ row_key: sailing.row_key, ...fields });
      onClose();
      flash('Booking request sent to the forwarders.');
    } catch (err) {
      setToast(`Could not send: ${err.message}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="modal-bg show"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="bk-title">
        {!reviewing ? (
          <div>
            <h3 id="bk-title">Enquire about this sailing</h3>
            <p className="msub">Fill the details, review the email, then send it to your forwarders.</p>
            <div className="bk-summary">
              <b>{vessel}</b>
              {voyage ? ` (${voyage})` : ''} — {sailing.carrier}
              <br />
              Nhava Sheva → {port}
              {sailing.country ? `, ${sailing.country}` : ''}
              <br />
              Departs {formatDate(sailing.etd) || '—'} · Arrives {formatDate(sailing.eta) || '—'}
              {transit}
            </div>
            <div className="bk-grid">
              <div className="control">
                <label className="lbl" htmlFor="bkStuff">Stuffing date</label>
                <input type="date" id="bkStuff" value={fields.stuffing} onChange={set('stuffing')} />
              </div>
              <div className="control">
                <label className="lbl" htmlFor="bkContainer">Containers</label>
                <input type="text" id="bkContainer" placeholder="e.g. 2 x 20 ft" value={fields.container} onChange={set('container')} />
              </div>
            </div>
            <div className="bk-grid" style={{ marginTop: 12 }}>
              <div className="control">
                <label className="lbl" htmlFor="bkNet">Net weight</label>
                <input type="text" id="bkNet" placeholder="e.g. 42,000 kg" value={fields.net_wt} onChange={set('net_wt')} />
              </div>
              <div className="control">
                <label className="lbl" htmlFor="bkGross">Gross weight</label>
                <input type="text" id="bkGross" placeholder="e.g. 44,500 kg" value={fields.gross_wt} onChange={set('gross_wt')} />
              </div>
            </div>
            <div className="bk-grid" style={{ marginTop: 12 }}>
              <div className="control bk-full">
                <label className="lbl" htmlFor="bkCommodity">Commodity</label>
                <input type="text" id="bkCommodity" value={fields.commodity} onChange={set('commodity')} />
              </div>
            </div>
            <div className="bk-grid" style={{ marginTop: 12 }}>
              <div className="control bk-full">
                <label className="lbl" htmlFor="bkRemarks">Target rate / remarks</label>
                <textarea id="bkRemarks" style={{ minHeight: 70 }} placeholder="Any target rate, free-time need, or note" value={fields.remarks} onChange={set('remarks')} />
              </div>
            </div>
            <Recipients forwarders={forwarders} />
            <div className="modal-actions">
              <button type="button" className="btn primary" onClick={() => setReviewing(true)}>
                Review request
              </button>
              <button type="button" className="btn ghost" onClick={onClose}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div>
            <h3 id="bk-title">Review &amp; send</h3>
            <p className="msub">This email goes to each forwarder separately — they won&apos;t see one another.</p>
            <div className="control">
              <label className="lbl" htmlFor="bkSubject">Subject</label>
              <input type="text" id="bkSubject" value={email.subject} readOnly />
            </div>
            <div className="control" style={{ marginTop: 12 }}>
              <label className="lbl" htmlFor="bkBody">Email</label>
              <textarea id="bkBody" value={email.body} readOnly />
            </div>
            <Recipients forwarders={forwarders} />
            <div className="mtoast" role="status">{toast}</div>
            <div className="modal-actions">
              <button type="button" className="btn primary" onClick={send} disabled={sending}>
                Send to forwarders
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={() => {
                  setReviewing(false);
                  setToast('');
                }}
              >
                Back to edit
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
