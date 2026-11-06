/* MY CUVAS admin bulk bar — shared by every admin list page with a
   bulk action. Checkboxes live OUTSIDE the row forms (rows already
   contain their own per-row forms, and nested forms are invalid), so
   this script gathers the ticked ids into the bulk form's hidden
   field on submit, shows the live selected count, and asks for
   confirmation. No submission ever happens with zero rows selected. */
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
  document.querySelectorAll('.bulk-select-all').forEach(function (sa) {
    sa.addEventListener('change', function () {
      document.querySelectorAll('.bulk-check').forEach(function (c) {
        c.checked = sa.checked;
      });
      updateCount();
    });
  });
  document.querySelectorAll('.bulk-check').forEach(function (c) {
    c.addEventListener('change', updateCount);
  });
  document.querySelectorAll('.bulk-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var ids = checkedIds();
      var hidden = form.querySelector('.bulk-ids');
      if (hidden) hidden.value = ids.join(',');
      if (!ids.length) {
        e.preventDefault();
        alert('Select at least one row first.');
        return;
      }
      var msg = '';
      var btn = e.submitter;
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
        if (!confirm(msg)) { e.preventDefault(); }
      }
    });
  });
  updateCount();
})();
