"use strict";
/* Apply the saved color theme and side-bar state before the page is drawn, so they do not
   flash. */
(function () {
  let theme = "cosmos";
  let nav = "expanded";
  try {
    const saved = window.localStorage.getItem("csv-tidy-theme");
    if (saved === "light" || saved === "cosmos") theme = saved;
    if (window.localStorage.getItem("csv-tidy-nav") === "collapsed") nav = "collapsed";
  } catch (error) {
    /* storage may be unavailable; keep the defaults */
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.nav = nav;
})();
