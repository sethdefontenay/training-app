# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Connecting Google Health (steps + sleep) from the Settings UI. OAuth offline access:
# the app captures a refresh token once and renews access tokens server-side thereafter.
# Secrets are stored server-side and never echoed back to the client.

Feature: Connect Google Health
  As Seth, who won't do manual admin,
  I want to connect Google Health once from Settings,
  so steps and sleep sync automatically from then on.

  Background:
    Given I am logged in
    And I am on the Settings screen

  Scenario: Starts disconnected
    When I view the Google Health connection
    Then it shows as not connected

  Scenario: Saving credentials never echoes the secrets back
    When I save my OAuth client ID and secret
    Then the screen reports which fields are set
    But it never returns the secret values

  Scenario: Connect with Google captures a refresh token
    Given I have saved my OAuth client ID and secret
    When I tap "Connect with Google" and grant offline access
    Then the app stores a refresh token
    And the connection shows as connected

  Scenario: Connecting before saving the client credentials is refused
    Given I have not saved a client ID
    When I tap "Connect with Google"
    Then I am told to save my client ID and secret first

  Scenario: A cancelled or failed consent is reported, not silently ignored
    When the Google consent is cancelled
    Then I am told the sign-in was cancelled

  Scenario: Pasting an existing refresh token also connects
    Given I already have a refresh token from elsewhere
    When I save the client ID, secret and refresh token directly
    Then the connection shows as connected

  Scenario: Once connected, a sync pulls steps and sleep
    Given Google Health is connected
    When a sync runs
    Then steps and sleep are pulled using a freshly refreshed access token


Feature: Connect Tidepool
  As Seth, I want to save my Tidepool login once,
  so the app pulls my glucose + insulin from the Tidepool API automatically.

  Scenario: Save Tidepool credentials and connect
    Given I am logged in and on the Settings screen
    When I save my Tidepool email and password
    Then Tidepool shows as connected
    But the password is never returned to the client

  Scenario: Pull glucose and insulin from the Tidepool API
    Given Tidepool is connected
    When I pull (or a check-in runs)
    Then the app logs in, fetches the data-model records, and stores glucose + insulin
