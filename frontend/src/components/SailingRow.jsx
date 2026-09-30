import { destination, formatDate, formatTransit, isLeavingSoon, shipTypeLabel } from '../lib/format.js';

/**
 * One sailing in the finder list.
 *
 * Reads as a card on a phone and as a row on a desktop — same markup, the grid
 * in app.css does the rest.
 *
 * The Direct/Indirect tag comes from the server's ship_type; an unlabelled
 * sailing gets no tag rather than a guess.
 */
export default function SailingRow({ sailing }) {
  const routing = shipTypeLabel(sailing.ship_type);
  const soon = isLeavingSoon(sailing.etd);

  return (
    <li className="sailing">
      <div className="sailing-carrier">
        <span className="carrier-name">{sailing.carrier}</span>
        {sailing.voyage_no ? <span className="voyage">{sailing.voyage_no}</span> : null}
        {routing ? (
          <span className={`tag tag-${sailing.ship_type}`}>{routing}</span>
        ) : null}
      </div>

      <div className="sailing-dest">
        <span className="dest-port">{destination(sailing)}</span>
        {sailing.vessel_name ? <span className="vessel">{sailing.vessel_name}</span> : null}
      </div>

      <div className="sailing-when">
        <span className="when">
          <span className="when-label">ETD</span>
          <span className="when-value">{formatDate(sailing.etd)}</span>
          {soon ? <span className="badge-soon">Leaving soon</span> : null}
        </span>
        <span className="when">
          <span className="when-label">ETA</span>
          <span className="when-value">{formatDate(sailing.eta)}</span>
        </span>
      </div>

      <div className="sailing-transit">{formatTransit(sailing.transit_days)}</div>
    </li>
  );
}
