# Behaviour spec — written before implementation (BDD-first). Declarative style.
# The weekly check-in is the app's killer output: assemble everything my PT asks for,
# accurately and with little effort. Pressing the check-in button gathers the relevant
# data from the LAST 7 DAYS (a rolling window ending today), not a fixed calendar week.
# The PT's own form/platform is outside this app — the app assembles correct data that's
# trivial to transfer.

Feature: Weekly PT check-in
  As Seth, doing my weekly check-in with my PT,
  I want one button to gather the last 7 days, accurately and with little effort,
  so the check-in takes a couple of minutes and the numbers are right.

  Background:
    Given I am logged in
    And I start a weekly check-in on 2026-05-25

  Scenario: Starting the check-in gathers the last 7 days of data
    When I start the weekly check-in
    Then it collects the relevant data from the 7 days ending today
    And the window is 2026-05-19 to 2026-05-25

  Scenario: Assemble what my PT asks for
    When I start the weekly check-in
    Then it includes my latest body measurements
    And the last 7 days of energy, motivation, stress and hunger
    And a place for posed photos
    And fields for "what I worked on" and "struggles"

  Scenario: The /10 metrics show the 7-day values and an average
    Given I logged daily energy, motivation, stress and hunger over the last 7 days
    When I start the weekly check-in
    Then I see each metric's daily values across those 7 days
    And a 7-day average for each metric

  Scenario: Measurements pre-fill from the last 7 days
    Given I recorded measurements on 2026-05-25
    When I start the weekly check-in
    Then those measurements are pre-filled

  Scenario: Shows the last recorded value for every body metric
    Given I last recorded each body metric on various recent dates
    When I start the weekly check-in
    Then I see the most recent value for each metric (waist, tummy, bum, thighs, weight)

  Scenario: Shows recovery context — average steps/day and sleep quality
    Given steps and sleep synced over the last 7 days
    When I start the weekly check-in
    Then I see my average steps per day
    And my average sleep duration and efficiency for the window

  Scenario: Enter today's measurements from the check-in
    When I fill in today's measurements grid and save
    Then today's measurements are recorded
    And the check-in's last-measurement values update

  Scenario: Attach posed photos to the check-in
    When I add posed photos
    Then they are saved with this check-in

  Scenario: A past check-in keeps its photos
    Given a completed check-in from a previous week with photos
    When I open that past check-in
    Then its photos are still viewable
    # attach-only: no side-by-side comparison view in v1

  Scenario: Reflections are mine to write, with the week's context surfaced to help
    When I start the weekly check-in
    Then I see the last 7 days of logged sessions and adherence as context
    And I can write "what I worked on" and "struggles" freely

  Scenario: Only photos and reflections need manual input
    Given measurements and daily /10s are already captured for the last 7 days
    When I start the weekly check-in
    Then everything else is pre-filled
    And only photos and the two reflections remain for me to add

  Scenario: Missing daily logs are shown honestly, never faked
    Given I did not log wellbeing on some of the last 7 days
    When I start the weekly check-in
    Then the values and average reflect only the days I actually logged
    And the missing days are shown as missing, not counted as zero

  Scenario: Glucose and insulin stay in my record, not in my PT's package
    Given Tidepool glucose and insulin were pulled for the last 7 days
    When I assemble the check-in
    Then glucose and insulin are not part of what I transfer to my PT
    And they remain in my own record

  Scenario: The completed check-in is presented for transfer to my PT
    Given the check-in is complete
    When I finish it
    Then I can view, copy or export it to fill in my PT's form
