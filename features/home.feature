# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Home is the hub you land on after login. It launches both the daily anchor (Today)
# and the non-daily areas (weekly shopping list, weekly check-in, measurements, etc.).

Feature: Home hub
  As Seth opening the app,
  I want one hub that gets me to today and to the not-daily things,
  so everything is one tap away and nothing hides.

  Background:
    Given I am logged in

  Scenario: Logging in lands on Home
    When I open the app and log in
    Then I am on the Home hub

  Scenario: Home gets me to today's tasks
    Given I am on the Home hub
    When I open "Today"
    Then I am on today's daily task list

  Scenario: Home gets me to the non-daily areas
    Given I am on the Home hub
    Then I can reach the weekly shopping list
    And I can reach the weekly check-in
    And I can reach my measurements
    And I can reach my exercise history
    And I can reach my current plan
    And I can reach settings

  Scenario: Home highlights today at a glance
    Given I am on the Home hub
    Then I see a quick status for today
    And today's tasks are the most prominent thing
