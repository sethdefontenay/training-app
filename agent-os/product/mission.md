# Product Mission

## Problem

Personal training is currently logged in an Obsidian vault synced between desktop and an Android phone via Syncthing. Keeping Syncthing alive is a constant maintenance burden, and the sync is fragile — exactly the wrong failure mode for data that gets entered on a phone, at the gym, mid-session. The training data is already tabular (sets, sessions, measurements, steps, sleep), so the free-form notes/wiki-linking of Obsidian buys little while the sync tax is paid daily.

On top of that, keeping the system current takes manual admin: pulling in steps/sleep, maintaining plans, generating shopping lists. The goal is a system that runs with **minimal manual admin** for the user.

## Target Users

A single user — Seth. One secure login, no multi-tenant complexity. (A read-only coach view, e.g. for "the PT", is a possible future addition but is explicitly out of scope for v1.)

## Solution

A hosted, mobile-first web app (installable PWA) backed by a single API + database, so the phone and desktop both hit the same backend and the sync problem disappears entirely.

What makes it worth building rather than tolerating Obsidian:

- **Progressive-overload "last week" column** (the feature that triggered the pivot): on the logging screen, each exercise shows the most recent prior session's top set (`weight×reps`) right next to the input, resolved correctly across skipped or shifted sessions.
- **Minimal manual admin:** health data (steps + sleep) syncs automatically from Fitbit/Google rather than being entered by hand. This is a v1 requirement, not a later add-on.
- **All-in-one:** training logging, automated health sync, and nutrition (meal plan + shopping list) live in one app instead of being scattered across an Obsidian vault and external tools.
- **No data loss:** the full Obsidian history (weeks of existing logs) is migrated into the database, so nothing already recorded is thrown away.
