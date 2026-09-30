/**
 * One sailing in the finder list.
 *
 * PLACEHOLDER — markup comes from reference/Index.html, not supplied yet.
 *
 * Shows: carrier, voyage, a Direct/Indirect tag (lib/format.js shipType),
 * destination, ETD/ETA, transit days, a "Leaving soon" badge when the ETD is
 * within 3 days, and the Enquire button.
 */
export default function SailingRow({ sailing }) {
  return <li className="sailing-row">{sailing?.row_key ?? 'Sailing — pending reference/Index.html.'}</li>;
}
