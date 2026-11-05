"use strict";
/* Apply the saved color theme and side-bar state before the page is drawn, so they do not
   flash. */
(function () {
  let theme = "cosmos";
  let nav = "expanded";
  /* Migration: Datakrit was called CSV Tidy until 1.2.0, which kept these choices under
     csv-tidy-* keys. A choice saved under an old key moves to its new key when the new key
     is missing, and the old key is removed. */
  try {
    const store = window.localStorage;
    for (const name of ["theme", "nav", "howto"]) {
      const old = store.getItem("csv-tidy-" + name);
      if (old !== null && store.getItem("datakrit-" + name) === null) {
        store.setItem("datakrit-" + name, old);
        store.removeItem("csv-tidy-" + name);
      }
    }
  } catch (error) {
    /* storage may be unavailable; nothing to move */
  }
  try {
    const saved = window.localStorage.getItem("datakrit-theme");
    if (saved === "light" || saved === "cosmos") theme = saved;
    if (window.localStorage.getItem("datakrit-nav") === "collapsed") nav = "collapsed";
  } catch (error) {
    /* storage may be unavailable; keep the defaults */
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.nav = nav;
})();
