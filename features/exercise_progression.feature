# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Per-exercise progression over time. Uses the SAME "top set" definition as the
# last-week column: heaviest weight, ties → most reps; bodyweight → most reps.
# History spans plan blocks (re-planning never loses logged history).

Feature: Exercise progression
  As Seth, I want to see how an exercise has progressed over time,
  so I can tell whether I'm actually getting stronger.

  Background:
    Given I am logged in

  Scenario: View an exercise's top set over time
    Given I have logged "Leg Press Machine" across several sessions
    When I view the "Leg Press Machine" progression
    Then I see its top set for each session date, oldest to newest

  Scenario: Bodyweight exercise progression tracks reps
    Given I have logged "Crunches" (bodyweight) across several sessions
    When I view the "Crunches" progression
    Then I see the top-set reps for each session date

  Scenario: Progression spans plan blocks
    Given I logged "Leg Press Machine" under the plan dated 2026-05-21
    And I logged it again under the plan dated 2026-07-02
    When I view the "Leg Press Machine" progression
    Then I see sessions from both plans in one continuous history

  Scenario: An exercise with no history shows nothing yet
    Given I have never logged "Hip Thrust"
    When I view the "Hip Thrust" progression
    Then I see that there is no history yet

  # --- Browsing & visualizing progression ---

  Scenario: Exercises are organised by training plan and workout day
    Given my current plan has training days each with their exercises
    When I open the exercise progress area
    Then the exercises are listed grouped under their workout day

  Scenario: Selecting an exercise visualizes its weight over time
    Given I have logged "Leg Press Machine" across several sessions
    When I select "Leg Press Machine"
    Then I see a chart of its top weight per workout day over time

  Scenario: Selecting a bodyweight exercise visualizes reps over time
    Given I have logged "Crunches" (bodyweight) across several sessions
    When I select "Crunches"
    Then I see a chart of its best reps per workout day over time
