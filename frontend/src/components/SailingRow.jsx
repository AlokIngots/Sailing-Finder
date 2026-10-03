import { formatShort, isLeavingSoon, shipTypeLabel, tidyVessel } from '../lib/format.js';

/**
 * One sailing card — the `.sail` markup from reference/Index.html.
 *
 * The Direct/Indirect tag comes from the server's ship_type; an unlabelled
 * sailing gets no tag rather than a guess. Enquire is internal-only, so it
 * drops out in Customer view.
 */
export default function SailingRow({ sailing, onEnquire }) {
  const { vessel, voyage } = tidyVessel(sailing);
  const routing = shipTypeLabel(sailing.ship_type);
  const soon = isLeavingSoon(sailing.etd);
  const port = sailing.pod_name || sailing.pod_code;

  return (
    <div className="sail">
      <div className="left">
        <div className="vessel">{vessel}</div>
        <div className="sub">
          <span className="tag">{sailing.carrier}</span>
          {voyage ? <span>{voyage}</span> : null}
          {routing ? <span className={`ttag ${sailing.ship_type}`}>{routing}</span> : null}
          <span className="dest">
            to {port}
            {sailing.country ? `, ${sailing.country}` : ''}
          </span>
          {soon ? (
            <span className="soon">
              <i />
              Leaving soon
            </span>
          ) : null}
        </div>
      </div>

      <div className="right">
        <div className="dt">
          <div className="k">Departs</div>
          <div className="v">{formatShort(sailing.etd)}</div>
        </div>
        <div className="dt">
          <div className="k">Arrives</div>
          <div className="v">{formatShort(sailing.eta)}</div>
          {Number.isFinite(sailing.transit_days) ? (
            <div className="transit">{sailing.transit_days} days transit</div>
          ) : null}
        </div>
      </div>

      <button type="button" className="btn primary bookbtn internal" onClick={() => onEnquire(sailing)}>
        Enquire
      </button>
    </div>
  );
}
