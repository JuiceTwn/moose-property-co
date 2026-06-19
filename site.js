// Mobile menu toggle — shared across all pages.
(function () {
  var nav = document.querySelector('nav');
  if (!nav) return;
  var burger = nav.querySelector('.burger');
  if (!burger) return;

  function close() {
    nav.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
  }

  burger.addEventListener('click', function () {
    var open = nav.classList.toggle('open');
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  // Close when a menu link is tapped, or on Escape.
  nav.querySelectorAll('.mobilemenu a').forEach(function (a) {
    a.addEventListener('click', close);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });
})();
