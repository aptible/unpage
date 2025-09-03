if (window.location.hostname.indexOf("localhost") == -1) {
  (function (a, p, t, i, b, l, e) {
    a.aptible = a.aptible || { _q: [] }; f = 'event,identify'.split(',');
    l = function (n) { return function () { a.aptible._q.push([n, Array.prototype.slice.call(arguments)]) } };
    for (e = 0; e < f.length; e++) { a.aptible[f[e]] = l(f[e]) };
    i = p.createElement(t); i.type = 'text/javascript'; i.async = 1; i.src = "https://minnow.unpage.ai/minnow.js";
    b = p.getElementsByTagName(t)[0]; b.parentNode.insertBefore(i, b);
  })(window, document, 'script');
  aptible.event('pageview');

  function addPushStateListener(listener) {
    if (!Proxy) return;
    window.history.pushState = new Proxy(window.history.pushState, {
      apply: (target, thisArg, argArray) => {
        target.apply(thisArg, argArray);
        listener();
      },
    });
  }

  addPushStateListener(() => {
    aptible.event('pageview');
  });
};
