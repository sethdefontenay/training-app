# Behaviour spec — written before implementation (BDD-first). Declarative style.
# The "Current plan" area: an aggregated, read-only view of the active plan.

Feature: Current plan detail
  As Seth reviewing my current plan,
  I want one screen aggregating my training days, meals, mobility and how long I've been on it,
  so I can see the whole plan at a glance.

  Background:
    Given I am logged in
    And an active plan is in place, started on 2026-05-21

  Scenario: See how long I've been on the plan
    When I open the current plan
    Then I see the plan's start date
    And how many days I've been on it

  Scenario: See the weekly schedule
    When I open the current plan
    Then I see each weekday mapped to its training day (or rest) and whether mobility is scheduled

  Scenario: See each training day's exercises
    When I open the current plan
    Then I see each training day with its exercises, sets × reps and prescribed weights

  Scenario: See the meals with macros
    When I open the current plan
    Then I see each meal with its calories and macros

  Scenario: Expand a meal to see its ingredient weights and amounts
    Given a meal "Protein oats" with ingredients
    When I open that meal from the plan
    Then I see each ingredient with its quantity and unit (e.g. "80 g oats")

  Scenario: See the daily targets
    When I open the current plan
    Then I see the steps, water, electrolyte and macro targets

  Scenario: No active plan
    Given there is no active plan
    When I open the current plan
    Then I am told there is no plan yet
