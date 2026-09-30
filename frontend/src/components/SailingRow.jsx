import { fmtShort, isLeavingSoon, shipTypeLabel, tidy } from '../lib/format.js';

/**
 * One sailing — a straight port of the reference's `.sail` block.
 *
 * The vessel name is the heading and the carrier is a tag beside it, which is
 * the reference's ordering, not ours. Dates are short ("5 Oct"): the year is
 * noise on a list that only ever holds today and the next few weeks.
 *
 * `.right` collapses under 600px via the reference's media query — same markup,
 * no separate mobile layout.
 */
export default function SailingRow({ sailing, onEnquire }) {
  const { vessel, voyage } = tidy(sailing);
  const routing = shipTypeLabel(sailing.ship_type);
  const soon = isLeavingSoon(sailing.etd);

  return (
    <div className="sail">
      <div className="left">
        <div className="vessel">{vessel}</div>
        <div className="sub">
          <span className="tag">{sailing.carrier}</span>
          {voyage ? <span>{voyage}</span> : null}
          {routing ? <span className={`ttag ${sailing.ship_type}`}>{routing}</span> : null}
          <span className="dest">
            to {sailing.pod_name || sailing.pod_code}, {sailing.country}
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
          <div className="v">{fmtShort(sailing.etd)}</div>
        </div>
        <div className="dt">
          <div className="k">Arrives</div>
          <div className="v">{fmtShort(sailing.eta)}</div>
          {sailing.transit_days != null ? (
            <div className="transit">{sailing.transit_days} days transit</div>
          ) : null}
        </div>
      </div>

      <button
        type="button"
        className="btn primary bookbtn internal"
        onClick={() => onEnquire(sailing)}
      >
        Enquire
      </button>
    </div>
  );
}
