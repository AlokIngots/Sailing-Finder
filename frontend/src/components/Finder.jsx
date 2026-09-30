/**
 * The finder view.
 *
 * PLACEHOLDER. The layout, controls and interactions come straight from
 * reference/Index.html, which has not been supplied — so nothing has been
 * invented here. See reference/README.md.
 *
 * What goes in, once it is:
 *   - cascading filters: Country -> Port -> Carrier
 *   - two date ranges: Departs between, Arrives between
 *   - segmented toggles: All / Direct / Indirect, and All sailings / Next per port
 *   - sort: soonest departure | fastest transit | soonest arrival
 *   - action row: Reset, Copy list, Download (CSV), WhatsApp, Email these
 *   - Customer view toggle, hiding the .internal elements
 *   - an Enquire button per sailing, opening EnquiryModal
 *
 * Data comes from api.schedule(filters) only — never from the sheet.
 */
export default function Finder() {
  return <section className="finder">Finder — pending reference/Index.html.</section>;
}
