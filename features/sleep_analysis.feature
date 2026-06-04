# Behaviour spec — Sleep analysis page. Sleep stages come from Google Health (Fitbit etc.):
# per-night stage segments (when each stage occurred) + per-stage totals, and weekly trends.
# Stage segments are captured on sync; nights synced before capture / from trackers that
# don't report stages show totals only.

Feature: Sleep analysis
  As Seth, I want to see my sleep stages per night and my weekly sleep trends,
  so I can understand and improve my sleep.

  Background:
    Given I am logged in

  Scenario: Stage segments are captured on sync
    Given Google Health returns a night with light, deep and REM stages
    When the sleep sync runs
    Then the per-stage totals and the stage segments (with their times) are stored

  Scenario: View a night's stage timeline
    Given a stored night with stage segments
    When I open the sleep page for that night
    Then I see each stage on a timeline showing when it occurred and for how long
    And I see the per-stage totals, bedtime, wake time and efficiency

  Scenario: A night without stage detail is shown honestly
    Given a stored night with totals but no stage segments
    When I open the sleep page for that night
    Then I see the totals and a note that stage detail isn't available

  Scenario: Weekly sleep trends
    Given stored nights across the last two weeks
    When I open the sleep page
    Then I see per-night stage breakdown and averages (asleep, efficiency, deep, REM)

  Scenario: Pick a different night
    Given several stored nights
    When I select another night
    Then its stage timeline and totals are shown
