/* Screenshots are dropped into docs/images/walkthrough/ as they are taken.
   Until one exists the browser would show a broken-image icon and say nothing
   useful, so each missing shot becomes a panel naming the file and what belongs
   in it. That is what makes the tutorial readable before any shot exists, and
   what makes a missing shot obvious rather than silent.

   The contract for what each one contains is images/walkthrough/SHOTS.md,
   generated from the data-shot / data-capture attributes below. */
(function () {
  function placeholder(fig) {
    var img = fig.querySelector("img");
    if (!img || fig.dataset.replaced) return;
    fig.dataset.replaced = "1";
    var box = document.createElement("div");
    box.className = "ph";
    box.innerHTML =
      '<span class="n">Screenshot</span>' +
      '<span class="f">images/walkthrough/' + (fig.dataset.shot || "") + "</span>" +
      '<span class="w">' + (fig.dataset.capture || img.alt || "") + "</span>";
    img.replaceWith(box);
  }

  function run() {
    document.querySelectorAll("figure.shot").forEach(function (fig) {
      var img = fig.querySelector("img");
      if (!img) return;
      if (img.complete && img.naturalWidth === 0) placeholder(fig);
      else img.addEventListener("error", function () { placeholder(fig); });
    });
  }

  /* Material loads pages through its instant-navigation router, so binding once
     on DOMContentLoaded would cover only the first page visited. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(run);
  }
})();
