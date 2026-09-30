# reference/ — source of truth

Two files belong in this folder. They are the source of truth for the port and
must not be edited:

| File        | What it defines                                                               |
|-------------|-------------------------------------------------------------------------------|
| `Index.html` | The exact UI — finder, enquiry modal, My bookings, the 3-step shipment screen. `frontend/` must match it pixel-for-pixel. |
| `Code.gs`    | The exact backend behaviour — schedule read, email, WhatsApp, enquiry → quotes → documents. `backend/src/` re-implements it. |

**Both files are still missing.** They were not on this machine when the scaffold
was built, so `frontend/index.html`, `frontend/css/styles.css` and
`frontend/js/app.js` are placeholders only — no UI has been invented in their
absence.

Drop the two files in here (export them from the Apps Script project:
*Extensions → Apps Script*, then copy `Index.html` and `Code.gs`), and the
frontend split can be done for real.
