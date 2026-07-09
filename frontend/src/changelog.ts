/** App changelog. Add a new entry at the TOP for each release and bump its version.
 * The modal (ChangelogModal) shows the latest entry the first time a returning user
 * opens the app after the version advances. CURRENT_VERSION is always the top entry. */

export type Release = { version: string; date: string; changes: string[] };

export const CHANGELOG: Release[] = [
  {
    version: "1.1.0",
    date: "2026-07-09",
    changes: [
      "Multi-user support — invite-only sign-up, with your data private to your account.",
      "Workout planner — build your own programs, add exercises (including custom ones), and assign a program to each weekday. It drives your daily view, falling back to your PT plan.",
      "The hub assistant can now build and edit your workout programs by voice or text.",
      "Voice input — tap the mic in the hub to speak instead of type.",
    ],
  },
];

export const CURRENT_VERSION = CHANGELOG[0].version;
