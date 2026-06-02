# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Cross-cutting navigation: every screen offers "home" and "back one step".
# HOME = the Home hub (a separate dashboard/launcher), NOT the daily task list.
# Some areas are not daily-centric (weekly shopping list, PT check-in), so Home is
# the place they all hang off.

Feature: Navigation
  As Seth moving around the app on my phone,
  I want a home control and a back-one-step control on every screen,
  so I never get stuck and can always get back to the hub.

  Background:
    Given I am logged in

  Scenario Outline: Every screen offers home and back
    Given I am on the "<screen>" screen
    Then a "home" control is available
    And a "back" control is available

    Examples:
      | screen              |
      | daily task list     |
      | workout logging     |
      | exercise history    |
      | measurements        |
      | weekly shopping list|
      | weekly check-in     |
      | plan review         |
      | settings            |

  Scenario: Home returns to the Home hub from anywhere
    Given I have navigated into "exercise history"
    When I tap "home"
    Then I am on the Home hub

  Scenario: Back returns to the previous screen
    Given I opened "exercise history" from the "workout logging" screen
    When I tap "back"
    Then I am on the "workout logging" screen

  Scenario: Back steps through the trail one screen at a time
    Given I went Home → daily task list → workout logging
    When I tap "back"
    Then I am on the daily task list
    And when I tap "back" again
    Then I am on the Home hub

  Scenario: Back on the Home hub does nothing destructive
    Given I am on the Home hub
    When I tap "back"
    Then I stay on the Home hub
    And nothing is lost
