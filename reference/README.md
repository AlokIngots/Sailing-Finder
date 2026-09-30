# reference/ — source of truth

Two files belong in this folder. They are the source of truth for the port and
must not be edited:

| File         | What it defines                                                               |
|--------------|-------------------------------------------------------------------------------|
| `Index.html` | The exact UI — finder, enquiry modal, My bookings, the 3-step shipment screen. The React components must reproduce it faithfully, and its CSS is ported into `frontend/src/styles/app.css` as-is where possible. |
| `Code.gs`    | The exact backend behaviour — schedule read, email, WhatsApp, enquiry → quotes → documents. Re-implemented in `backend/app/`. |

**Both files are still missing.** They were not in this folder when the scaffold
was built, so every React component is a labelled placeholder and `app.css`
carries only the brand foundation — no UI has been invented in their absence.

Export them from the Apps Script project (*Extensions → Apps Script*, then copy
`Index.html` and `Code.gs`) and drop them in here. The port can then be done for
real.
