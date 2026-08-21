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

// Background job clips — load only when seen, and only when the connection
// and the visitor's motion preference say it is welcome. No clip means no cost:
// the markup ships with preload="none" and no src at all.
(function () {
  var clips = document.querySelectorAll('video[data-src]');
  if (!clips.length) return;

  var conn = navigator.connection || {};
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var thrifty = conn.saveData === true || /2g/.test(conn.effectiveType || '') || reduced;

  function attach(v) {
    if (!v.src) v.src = v.getAttribute('data-src');
  }

  // Data Saver, a slow connection, or reduced-motion: never autoplay. Attaching
  // the src is still free here — preload="none" holds the download until play.
  if (thrifty || !('IntersectionObserver' in window)) {
    clips.forEach(function (v) { attach(v); v.controls = true; });
    return;
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      var v = e.target;
      if (e.isIntersecting) {
        attach(v);
        var p = v.play();
        // Autoplay can still be refused (iOS Low Power Mode); give them controls.
        if (p && p.catch) p.catch(function () { v.controls = true; });
      } else if (!v.paused) {
        v.pause();
      }
    });
  }, { threshold: 0.25 });

  clips.forEach(function (v) { io.observe(v); });
})();
