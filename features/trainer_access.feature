# Behaviour spec — read-only "trainer" (coach) login. Seth's PT gets her own account
# that can VIEW every area except settings, and can use the assistant chat (read tools
# only), but can never mutate data. The security boundary is enforced server-side; the
# frontend also hides write controls and the settings area (UI-only, not covered here).

Feature: Read-only trainer access
  As Seth, sharing my data with my PT,
  I want her to have her own login that can see everything except settings but change nothing,
  so she can review my progress without any risk of altering my records.

  Background:
    Given a read-only trainer account and a full-access owner account exist

  Scenario: The trainer can read any area
    Given I am logged in as the trainer
    When I open today's list
    Then I can read it
    And I can read my workout history

  Scenario: The trainer cannot change anything
    Given I am logged in as the trainer
    When the trainer tries to start a workout session
    Then the change is refused as forbidden
    When the trainer tries to log wellbeing
    Then the change is refused as forbidden

  Scenario: The trainer cannot reach settings at all
    Given I am logged in as the trainer
    When the trainer opens the settings integrations
    Then access is refused as forbidden

  Scenario: The owner keeps full access
    Given I am logged in as the owner
    When I start a workout session
    Then it is created
    And I can read the settings integrations

  Scenario: The trainer may use the assistant chat
    Given I am logged in as the trainer
    When the trainer sends a message to the assistant
    Then the request is not refused as forbidden

  Scenario: The trainer's assistant cannot make changes
    Given I am logged in as the trainer
    When the trainer's assistant runs
    Then it is offered only read tools, never write tools

  Scenario: The account role is reported
    Given I am logged in as the trainer
    Then my role is reported as "trainer"
    Given I am logged in as the owner
    Then my role is reported as "owner"
