/**
 * The bottom-centre toast from reference/Index.html.
 *
 * Kept as a plain function driving a single #flash element, the way the
 * reference does, rather than React state threaded through every component —
 * one message at a time, from anywhere, replacing whatever was there.
 */

let timer = null;

export function flash(message) {
  const el = document.getElementById('flash');
  if (!el) return;

  el.textContent = message;
  el.classList.add('show');
  clearTimeout(timer);
  timer = setTimeout(() => el.classList.remove('show'), 4500);
}

export default flash;
