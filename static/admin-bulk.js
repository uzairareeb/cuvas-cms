/* MY CUVAS admin bulk bar — shared by every admin list page with a
   bulk action. Checkboxes live OUTSIDE the row forms (rows already
   contain their own per-row forms, and nested forms are invalid), so
   this script gathers the ticked ids into the bulk form's hidden
   field on submit, shows the live selected count, and asks for
   confirmation. Confirmation is INLINE (two-step button), never a
   native window.confirm()/alert() dialog: automated browsers
   auto-dismiss those dialogs, so the old confirm() call returned
   false and the first click silently did nothing at all (live bug
   2026-11-06 — bars rendered and counts updated, but no POST ever
   happened). No submission ever happens with zero rows selected. */
(function () {
  function checkedIds() {
    var ids = [];
    document.querySelectorAll('.bulk-check:checked').forEach(function (c) {
      ids.push(c.value);
    });
    return ids;
  }
  function updateCount() {
    var n = checkedIds().length;
    document.querySelectorAll('.bulk-count').forEach(function (el) {
      el.textContent = n + ' selected';
    });
  }
  function disarmAll() {
    document.querySelectorAll('.bulk-form [data-armed="1"]').forEach(function (b) {
      b.removeAttribute('data-armed');
      if (b.dataset.origLabel !== undefined) { b.textContent = b.dataset.origLabel; }
      if (b._bulkTimer) { clearTimeout(b._bulkTimer); b._bulkTimer = null; }
    });
    updateCount();
  }
  function showNote(form, text) {
    var el = form.querySelector('.bulk-count');
    if (el) el.textContent = text;
  }
  document.querySelectorAll('.bulk-select-all').forEach(function (sa) {
    sa.addEventListener('change', function () {
      document.querySelectorAll('.bulk-check').forEach(function (c) {
        c.checked = sa.checked;
      });
      disarmAll();
    });
  });
  document.querySelectorAll('.bulk-check').forEach(function (c) {
    c.addEventListener('change', function () { disarmAll(); });
  });
  document.querySelectorAll('.bulk-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var ids = checkedIds();
      var hidden = form.querySelector('.bulk-ids');
      if (hidden) hidden.value = ids.join(',');
      if (!ids.length) {
        e.preventDefault();
        showNote(form, 'Select at least one row first.');
        setTimeout(updateCount, 4000);
        return;
      }
      var btn = e.submitter || form.querySelector('button[type="submit"]');
      var msg = '';
      if (btn && btn.getAttribute('data-confirm')) {
        msg = btn.getAttribute('data-confirm');
      } else if (form.getAttribute('data-confirm')) {
        msg = form.getAttribute('data-confirm');
      }
      if (msg) {
        msg = msg.replace('{n}', ids.length);
        var sel = form.querySelector('select[name="status"], select[name="target"]');
        if (sel && sel.options.length) {
          msg = msg.replace('{target}', sel.options[sel.selectedIndex].text);
        }
      }
      if (btn && msg && btn.getAttribute('data-armed') !== '1') {
        /* First click: arm only. Show exactly what will happen in
           the bar and ask for a second click on the same button.
           Never a native dialog, so nothing can silently swallow it. */
        e.preventDefault();
        disarmAll();
        btn.setAttribute('data-armed', '1');
        btn.dataset.origLabel = btn.textContent;
        btn.textContent = 'Click again to confirm';
        showNote(form, msg + ' — click again to confirm.');
        btn._bulkTimer = setTimeout(disarmAll, 6000);
        return;
      }
      if (btn && btn.getAttribute('data-armed') === '1') {
        btn.removeAttribute('data-armed');
        if (btn._bulkTimer) { clearTimeout(btn._bulkTimer); btn._bulkTimer = null; }
      }
    });
  });
  updateCount();
})();
