# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Steps + sleep come from the existing google-health sync (Fitbit Sense 2 → Google Health,
# ported from catch_up.py). Steps target is 7,000/day. Sleep carries duration, efficiency,
# stages, bedtime/wake. Everything stays editable (manual override/fallback).

Feature: Steps and sleep sync
  As Seth, who won't log activity by hand,
  I want my steps and sleep to arrive automatically and stay correctable,
  so my dashboard and check-ins are current with no admin.

  Background:
    Given I am logged in
    And my steps and sleep sync is connected

  Scenario: A sync pulls recent steps and sleep
    When a sync runs
    Then the latest days of steps and sleep are stored

  Scenario: The sync runs on a daily schedule
    Given the scheduled sync time has arrived
    Then a sync runs automatically in the background

  Scenario: The sync also runs when I open the app
    When I open the app
    Then a sync runs to refresh today's steps and sleep

  Scenario: Steps are shown against the daily target
    Given 733 steps synced for 2026-05-25
    When I view 2026-05-25
    Then it shows 733 of 7,000 steps
    And the target is marked not met

  Scenario: Sleep stores duration, efficiency and stages
    Given a sleep record synced for 2026-05-25
    When I view that night
    Then it shows time asleep, efficiency, and the light/deep/REM/awake stages

  Scenario: Backfill catches up missed days
    Given no sync ran for 3 days
    When a sync runs
    Then steps and sleep for each of the missed days are filled in

  Scenario: Re-syncing a day updates it without duplicating
    Given steps for 2026-05-25 are already stored
    When a sync runs again for 2026-05-25
    Then the day's steps are updated in place
    And no duplicate day is created

  Scenario: A sync failure is surfaced, not silent
    Given the health source cannot be reached
    When a sync runs
    Then the failure is surfaced to me
    And the last good data is left untouched

  Scenario: I can correct or enter a day manually
    Given the sync missed 2026-05-24
    When I enter 8,200 steps for 2026-05-24 manually
    Then 2026-05-24 shows 8,200 steps
    And a later sync will not overwrite my manual entry without telling me
