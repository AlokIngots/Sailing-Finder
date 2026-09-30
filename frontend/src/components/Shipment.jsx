/**
 * The shipment screen — three stacked steps, each in a done / do-this-next /
 * waiting state.
 *
 * PLACEHOLDER — markup and the step states come from reference/Index.html,
 * not supplied yet.
 *
 *   1. Booking request   — the details, and who was emailed
 *   2. Quotes & pick     — type each forwarder's rate + note, save, then
 *                          Choose the cheapest; the winner is marked
 *   3. Send documents    — attach PL, CI and VGM, email them to the chosen
 *                          forwarder
 *
 * Rates and notes are operator-judgement fields: free text, never validated.
 */
export default function Shipment() {
  return <section className="shipment">Shipment — pending reference/Index.html.</section>;
}
