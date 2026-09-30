/**
 * The enquiry modal: details -> Review request -> Send to forwarders.
 *
 * PLACEHOLDER — markup and copy come from reference/Index.html and the email
 * body from reference/Code.gs. Neither has been supplied, so nothing has been
 * invented here.
 *
 * Fields: stuffing date, containers, net/gross weight, commodity,
 * target-rate/remarks. These are operator-judgement fields — free text, no
 * "that looks wrong" validation. Concerns get raised in conversation, not
 * enforced by the form.
 *
 * "Review request" shows the exact email before anything is sent.
 * "Send to forwarders" posts once to api.enquiry(); the server emails each of
 * the three forwarders separately.
 */
export default function EnquiryModal() {
  return <div className="modal">Enquiry — pending reference/Index.html.</div>;
}
