# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Diabetes data flows through ONE integration: Tidepool.
#   - Dexcom glucose: Tidepool pulls it (cloud).
#   - Tandem t:slim X2 pump: Seth uploads it to Tidepool via the Tidepool Uploader
#     (desktop app, pump on cable) — manually, weekly, before the check-in.
# The app pulls the last 7 days from Tidepool at check-in time, into SETH'S OWN RECORD.
# This data is NOT part of the package sent to the PT (their form is measurements/10s/
# photos/reflections) — it's for Seth's own history/dashboard.
# NOTE: Tidepool API access/auth to be verified against live docs before building.

Feature: Diabetes data via Tidepool
  As Seth managing Type 1 diabetes,
  I want my glucose and pump data gathered into my own record with almost no admin,
  so my diabetes history stays current and I don't hand-transcribe anything.

  Background:
    Given I am logged in
    And the app is connected to Tidepool
    And today is 2026-05-25

  Scenario: The check-in pulls the last 7 days of diabetes data
    When I start the weekly check-in
    Then the app pulls glucose and pump data for 2026-05-19 to 2026-05-25 from Tidepool

  Scenario: Opening my diabetes record pulls the latest from Tidepool
    When I open my diabetes record
    Then the app pulls the latest glucose and pump data from Tidepool
    And I see the most current data available

  Scenario: Dexcom glucose is stored from Tidepool
    Given Dexcom glucose for the last 7 days is available in Tidepool
    When the check-in pull runs
    Then those glucose readings are stored against their days

  Scenario: Tandem pump data is stored from Tidepool
    Given I uploaded my Tandem pump to Tidepool before the check-in
    When the check-in pull runs
    Then my insulin and pump data for the last 7 days are stored

  Scenario: Diabetes data is stored to my record
    Given glucose and pump data for the last 7 days are pulled
    When I view my diabetes record for the week
    Then it includes a glucose summary (average and time-in-range)
    And my insulin/pump data for the week

  Scenario: A missing pump upload is shown honestly, never faked
    Given I did not upload my Tandem pump to Tidepool this week
    When I start the weekly check-in
    Then the pump data is shown as not uploaded
    And the app reminds me to run the Tidepool Uploader
    And no insulin figures are invented

  Scenario: Re-pulling the same week is idempotent
    Given the diabetes data for this week is already pulled
    When the check-in pull runs again for the same week
    Then the data is updated in place
    And no duplicates are created

  Scenario: Tidepool being unreachable is surfaced, with manual fallback
    Given Tidepool cannot be reached
    When the check-in pull runs
    Then the failure is surfaced to me
    And I can enter the key figures manually if I need to

  Scenario: Upload a Tidepool data-model JSON export directly (no Tidepool cloud)
    Given a Tidepool data-model JSON export with glucose and bolus records
    When I upload it on the diabetes screen
    Then the glucose and insulin records are stored to my record
    And re-uploading the same file adds no duplicates

  Scenario: I can refresh diabetes data on demand before finishing the check-in
    Given I uploaded my pump to Tidepool after starting the check-in
    When I refresh the diabetes data
    Then the newly uploaded pump data is pulled and included
