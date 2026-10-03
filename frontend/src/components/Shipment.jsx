import { Link, useParams } from 'react-router-dom';

/**
 * The shipment screen — #v-shipment of reference/Index.html: three stacked
 * steps, each in a done / do-this-next / waiting state.
 *
 *   1. Booking request   — the details, and who was emailed
 *   2. Quotes & pick     — type each forwarder's rate + note, save, then
 *                          Choose the cheapest; the winner is marked
 *   3. Send documents    — attach PL, CI and VGM, email them to the chosen
 *                          forwarder
 *
 * PLACEHOLDER until the bookings API lands — only the reference's breadcrumb
 * and frame are here so the screen sits in the shell. Rates and notes are
 * operator-judgement fields: free text, never validated.
 */
export default function Shipment() {
  const { ref } = useParams();

  return (
    <div className="view active" id="v-shipment">
      <div className="wrap">
        <div className="crumb">
          <Link to="/bookings">My bookings</Link> <span>/</span> <span>{ref}</span>
        </div>
        <div className="empty" style={{ marginTop: 14 }}>
          <h3>Not available yet</h3>
          <div>Shipment steps arrive with the bookings feature.</div>
        </div>
        <div className="foot">One shipment, three steps — the screen only asks for what&apos;s next.</div>
      </div>
    </div>
  );
}
