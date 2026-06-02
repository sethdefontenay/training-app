# Behaviour spec — written before implementation (BDD-first). Declarative style.
# A non-daily area reached from Home. The weekly shopping list is generated from the
# active plan's meals — vault behaviour aggregates each meal's ingredients across the
# week (×7) by name + unit. Items are checkable as you shop.

Feature: Weekly shopping list
  As Seth doing a weekly shop,
  I want a list built from my plan's meals that I can tick off,
  so I buy exactly what the week needs with no manual list-making.

  Background:
    Given I am logged in
    And an active plan with meals and ingredients is in place

  Scenario: The shopping list is generated from the plan's meals
    When I open the weekly shopping list
    Then it lists the ingredients needed for the week
    And quantities are aggregated across meals for 7 days

  Scenario: Aggregate the same ingredient across meals
    Given two meals each use cooked chicken
    When I open the weekly shopping list
    Then the chicken appears once with the combined weekly quantity

  Scenario: Tick off items as I buy them
    When I check off "mixed nuts"
    Then "mixed nuts" is marked as bought
    And the checked state persists when I leave and return

  Scenario: A new plan regenerates the shopping list
    Given I approve a new plan with different meals
    When I open the weekly shopping list
    Then it reflects the new plan's ingredients
    # the previous week's checked state does not carry over to the new list

  Scenario: Reset the list for a new shopping trip
    Given I have checked off several items
    When I start a new shopping list for the week
    Then all items are unchecked again
