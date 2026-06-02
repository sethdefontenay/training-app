# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Mobility is a per-day round of exercises (from the plan), ticked off individually.
# Vault: Mobility-Done records date + exercise slug + the round it belonged to.

Feature: Mobility tracking
  As Seth, working through my mobility round,
  I want to tick off each movement,
  so my recovery work is tracked and counts toward the day.

  Background:
    Given I am logged in
    And today is 2026-05-22
    And today's plan includes a "Mobility" round with "Bird Dog", "Cat-Cow" and "Shoulder CARs"

  Scenario: See today's mobility round
    When I open today's mobility
    Then I see "Bird Dog", "Cat-Cow" and "Shoulder CARs" to do

  Scenario: Mark a mobility exercise done
    When I mark "Bird Dog" done
    Then "Bird Dog" is recorded as completed today
    And today's mobility shows 1 of 3 done

  Scenario: Completing every exercise completes the round
    When I mark "Bird Dog", "Cat-Cow" and "Shoulder CARs" done
    Then today's mobility round is complete

  Scenario: An unmarked exercise is not counted
    When I mark only "Bird Dog" done
    Then "Cat-Cow" and "Shoulder CARs" remain not done

  Scenario: Mobility completion counts toward the day's adherence
    Given I completed today's mobility round
    When I view today's adherence
    Then mobility shows as done
