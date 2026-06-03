// Service-worker registration with self-updating behaviour.
//
// registerType is "autoUpdate" (see vite.config.ts): when a new SW takes
// control the page reloads automatically — no manual cache clear. The catch is
// the browser only *checks* for a new SW on navigation, so a long-open PWA can
// sit on stale code. We force a check periodically and whenever the app regains
// focus (e.g. reopening the installed PWA), which is the common case here.
import { registerSW } from "virtual:pwa-register";

const CHECK_INTERVAL_MS = 60 * 60 * 1000; // hourly while open

const updateSW = registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, registration) {
    if (!registration) return;
    setInterval(() => void registration.update(), CHECK_INTERVAL_MS);
    // Check on tab focus / app resume so a freshly-deployed version is picked
    // up the next time you open the app, not an hour later.
    const checkOnFocus = () => {
      if (document.visibilityState === "visible") void registration.update();
    };
    document.addEventListener("visibilitychange", checkOnFocus);
    window.addEventListener("focus", checkOnFocus);
  },
});

export { updateSW };
