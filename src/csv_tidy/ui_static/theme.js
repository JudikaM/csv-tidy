"use strict";
/* Apply the saved color theme before the page is drawn, so it does not flash. */
(function () {
  let theme = "cosmos";
  try {
    const saved = window.localStorage.getItem("csv-tidy-theme");
    if (saved === "light" || saved === "cosmos") theme = saved;
  } catch (error) {
    /* storage may be unavailable; keep the default */
  }
  document.documentElement.dataset.theme = theme;
})();
