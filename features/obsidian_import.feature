# Behaviour spec — written before implementation (BDD-first). Declarative style.
# One-off-but-re-runnable importer: full Obsidian history → Postgres, losing nothing.
# Folder → table mapping and field shapes are known (see discovery.md / HANDOFF.md §5).
# Vault quirks: reps/weight stored as strings; empty weight = bodyweight.

Feature: Obsidian history import
  As Seth, migrating off Obsidian,
  I want my full training history imported,
  so I lose none of the weeks I've already logged and the app is useful from day one.

  Background:
    Given I am logged in
    And my Obsidian vault is available to the importer

  Scenario: Import the full history
    When I run the import
    Then my sessions, sets, measurements, steps, sleep and mobility records are loaded
    And each record keeps its original date

  Scenario: Bodyweight sets import with an empty weight
    Given a logged set with reps "15" and an empty weight
    When I run the import
    Then it is stored as a bodyweight set of 15 reps

  Scenario: The current Obsidian plan becomes the active plan block
    Given the vault has a meal/training plan marked current
    When I run the import
    Then it becomes my active plan

  Scenario: The import is re-runnable without duplicating
    Given I have already imported my history
    When I run the import again
    Then no duplicate records are created
    And records changed in the vault are updated in place

  Scenario: Unparseable files are reported, never silently dropped
    Given one record file is malformed
    When I run the import
    Then that file is listed in the import summary as needing attention
    And the rest of the import still completes

  Scenario: The import reports what it did
    When the import finishes
    Then I see counts of how many sessions, sets, measurements, steps, sleep and mobility records were imported

  Scenario: The last-week column works immediately after import
    Given my history is imported
    When I open today's session
    Then the last-week column shows numbers drawn from my imported history
