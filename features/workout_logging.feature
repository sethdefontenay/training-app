# Behaviour spec — written before implementation (BDD-first).
# Lives here during design; moves into backend/tests/features/ when we build.
# Examples use real numbers from the Obsidian vault (leg press 40×15, lat pulldown 47×15).

Feature: Workout logging
  As Seth, logging sets on my phone at the gym,
  I want to record each set quickly and see what I lifted last time,
  so I can apply progressive overload without doing mental arithmetic mid-session.

  Background:
    Given I am logged in
    And today is 2026-05-25
    And today's scheduled session is "Training Day 1"
    And "Training Day 1" prescribes "Leg Press Machine" at 4 × 15

  Scenario: Log a resistance set
    When I log a set for "Leg Press Machine" of 40 kg × 15 reps
    Then the set is saved against today's session
    And "Leg Press Machine" shows 1 of 4 sets completed

  Scenario: Log a bodyweight set (no weight)
    Given "Crunches" is a bodyweight exercise
    When I log a set for "Crunches" of 15 reps with no weight
    Then the set is saved with an empty weight
    And the set is displayed as "BW × 15"

  Scenario: Edit a logged set
    Given I logged "Leg Press Machine" of 40 kg × 15 reps
    When I change that set to 45 kg × 12 reps
    Then the set reads 45 kg × 12 reps
    And no extra set is created

  Scenario: Delete a logged set
    Given I have logged 2 sets for "Leg Press Machine"
    When I delete the second set
    Then "Leg Press Machine" shows 1 of 4 sets completed

  # ---------------------------------------------------------------------------
  # The progressive-overload "last week" column — the headline feature.
  # Shows ONLY the heaviest weight lifted in the most recent prior session (not reps).
  # Bodyweight moves have no weight — see the bodyweight scenario.
  # ---------------------------------------------------------------------------

  Scenario: Last-week shows the heaviest weight from the most recent prior session
    Given I logged "Leg Press Machine" on 2026-05-18, heaviest set 40 kg
    When I open today's session
    Then the "last week" column for "Leg Press Machine" shows "40 kg"

  Scenario: Last-week resolves to the most recent prior date, not exactly 7 days ago
    Given I logged "Lat Pulldown" on 2026-05-15, heaviest set 47 kg
    And I have not trained "Lat Pulldown" since
    When I open today's session
    Then the "last week" column for "Lat Pulldown" shows "47 kg"

  Scenario: Only the heaviest weight is shown — reps do not affect it
    Given on 2026-05-18 I logged these sets for "Leg Press Machine":
      | weight | reps |
      | 40     | 15   |
      | 45     | 12   |
      | 45     | 14   |
    When I open today's session
    Then the "last week" column for "Leg Press Machine" shows "45 kg"

  Scenario: Last-week for a bodyweight exercise shows "BW"
    Given I logged "Crunches" (bodyweight) on 2026-05-18
    When I open today's session
    Then the "last week" column for "Crunches" shows "BW"

  Scenario: No prior history shows a dash
    Given I have never logged "Hip Thrust"
    When I open today's session
    Then the "last week" column for "Hip Thrust" shows "—"

  Scenario: Today's own sets never count as "last week"
    Given I logged "Leg Press Machine" on 2026-05-18, heaviest set 40 kg
    And I have already logged 45 kg earlier in today's session
    When I view the "last week" column for "Leg Press Machine"
    Then it still shows "40 kg"

  Scenario: Workout history lists past sessions, newest first
    Given I logged workouts on several days
    When I open my workout history
    Then I see each logged day with its exercises and sets, most recent first
    And days with no logged sets are not shown

  # ---------------------------------------------------------------------------
  # One workout per day. The log-workout screen reuses today's session across
  # navigations rather than creating a fresh one, so nothing is lost or duplicated.
  # (The set-by-set guided runner — work/rest timers — is a client-side concern
  # over this same contract and is not covered here.)
  # ---------------------------------------------------------------------------

  Scenario: Starting today's workout twice reuses the same session
    When I start today's workout
    And I start today's workout again
    Then both refer to the same session for today

  Scenario: Reopening the workout keeps the sets already logged
    Given I logged 2 sets for "Leg Press Machine" today
    When I reload today's workout
    Then today's session still shows 2 logged sets for "Leg Press Machine"
