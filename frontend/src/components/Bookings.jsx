/**
 * My bookings — newest first, each with a status chip:
 * Request sent / Quotes in / Booked / Docs sent.
 *
 * PLACEHOLDER — markup comes from reference/Index.html, not supplied yet.
 *
 * The list is whatever api.bookings() returns; the server decides what this
 * user may see (their own, or everything for an admin). No filtering happens
 * here — a client-side filter would not be a security boundary.
 */
export default function Bookings() {
  return <section className="bookings">My bookings — pending reference/Index.html.</section>;
}
