import { formatShort, isLeavingSoon, shipTypeLabel, tidyVessel } from '../lib/format.js';

/**
 * One sailing as a row of the Find sailings table (table.sails in app.css).
 *
 * The Direct/Indirect tag comes from the server's ship_type; an unlabelled
 * sailing gets no tag rather than a guess. Enquire is internal-only, so its
 * cell drops out in Customer view (the header cell in Finder.jsx does too).
 */
export default function SailingRow({ sailing, onEnquire }) {
  const { vessel, voyage } = tidyVessel(sailing);
  const routing = shipTypeLabel(sailing.ship_type);
  const soon = isLeavingSoon(sailing.etd);
  const port = sailing.pod_name || sailing.pod_code;

  return (
    <tr>
      <td>
        <div className="vessel">{vessel}</div>
        <div className="sub">
          {sailing.carrier}
          {voyage ? ` · ${voyage}` : ''}
        </div>
      </td>
      <td>
        <div className="dest">
          to {port}
          {sailing.country ? `, ${sailing.country}` : ''}
        </div>
        {soon ? <div className="soon">• Leaving soon</div> : null}
      </td>
      <td>{routing ? <span className={`ttag ${sailing.ship_type}`}>{routing}</span> : null}</td>
      <td>
        <div className="date">{formatShort(sailing.etd)}</div>
      </td>
      <td>
        <div className="date">{formatShort(sailing.eta)}</div>
        {Number.isFinite(sailing.transit_days) ? (
          <div className="sub">{sailing.transit_days} days transit</div>
        ) : null}
      </td>
      <td className="act internal">
        <button type="button" className="btn primary sm" onClick={() => onEnquire(sailing)}>
          Enquire
        </button>
      </td>
    </tr>
  );
}
