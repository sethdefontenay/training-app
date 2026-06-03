# Behaviour spec — written before implementation (BDD-first). Declarative style.
# The daily task list is the anchor screen: open it each day to see what to do and
# eat, check things off, read carbs for the pump, and log how the day is going.

Feature: Daily task list
  As Seth, opening the app each morning,
  I want one screen showing today's activities, meals (with carbs), and a quick way
  to log how I feel,
  so that staying on plan needs almost no admin and I can dose insulin off the carb numbers.

  Background:
    Given I am logged in
    And an active plan is in place
    And today is Monday 2026-05-25
    And the schedule maps Monday to "Training Day 1" and "Mobility"

  # --- What today shows ---

  Scenario: Today reflects the active plan for today's weekday
    When I open today's list
    Then I see the workout "Training Day 1"
    And I see a "Mobility" round
    And I see today's four planned meals
    And I see the daily targets: 7,000 steps, 2–3 L water, 1 electrolyte serve

  Scenario: A rest day shows no workout but still meals, targets and wellbeing
    Given today is Sunday 2026-05-31
    And the schedule maps Sunday to no training
    When I open today's list
    Then I see no workout
    But I see today's planned meals
    And I see the daily wellbeing log

  # --- Meals & carbs (safety-relevant) ---

  Scenario: Each meal shows its carbs and the source of that number
    When I open today's list
    Then "Meal 1 — Breakfast" shows 74 g carbs
    And the carb figure is attributed to the active plan
    And the list shows a daily carb total of 212 g

  Scenario: Carb numbers on the daily list are read-only
    When I open today's list
    Then I cannot edit a meal's carbs from the daily list
    # Carbs only change when the plan changes, which is review-gated (see plan ingestion)

  Scenario: Checking a meal records adherence, not intake
    When I check off "Meal 1 — Breakfast" as eaten
    Then today records that the planned meal was eaten
    And the meal's carb figure is unchanged
    # Actual intake is reported to my PT via MyFitnessPal, outside this app

  Scenario: A checked meal can be un-checked
    Given I checked off "Meal 1 — Breakfast" as eaten
    When I un-check it
    Then today no longer records that meal as eaten

  # --- Activities & mobility ---

  Scenario: Workout progress reflects logged sets, not a manual tick
    Given "Training Day 1" prescribes "Leg Press Machine" at 4 × 15
    When I log 2 sets for "Leg Press Machine"
    Then today's list shows "Leg Press Machine" at 2 of 4 sets

  Scenario: A mobility section appears on workout days
    When I open today's list
    Then I see a mobility section with my mobility moves to tick off

  Scenario: A rest day shows no mobility section
    Given today is Sunday 2026-05-31 with no training scheduled
    When I open today's list
    Then there is no mobility section

  Scenario: Mobility moves are ticked off individually, and can be un-ticked
    Given today's mobility includes "Bird Dog"
    When I mark "Bird Dog" done
    Then today's list shows "Bird Dog" as completed
    When I un-mark "Bird Dog"
    Then "Bird Dog" is no longer completed

  # --- Daily wellbeing (feeds the weekly check-in) ---

  Scenario: Log the daily wellbeing scores inline
    When I set today's energy to 7, motivation to 6, stress to 4, and hunger to 5
    Then today's wellbeing is saved as energy 7, motivation 6, stress 4, hunger 5

  Scenario: Wellbeing scores are out of 10
    When I try to set today's energy to 11
    Then the entry is rejected

  Scenario: Today's wellbeing can be updated later in the day
    Given I logged today's energy as 7 this morning
    When I change today's energy to 5
    Then today's energy reads 5
    And no duplicate entry is created

  # --- Steps / water / notes ---

  Scenario: Steps progress comes from the synced step count
    Given 4,200 steps have synced for today
    When I open today's list
    Then the steps target shows 4,200 of 7,000

  Scenario: Water and electrolytes are manual ticks
    When I log 1 of my water targets and 1 electrolyte serve
    Then today shows water progress and the electrolyte serve as done

  Scenario: Capture an off-plan note for the day
    When I add a note "ate an extra banana pre-gym"
    Then today keeps that note
