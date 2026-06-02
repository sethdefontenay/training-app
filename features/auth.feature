# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Single user (just Seth). Holds medical data. Login = email + password, with a
# long-lived session on the trusted phone (JWT). Low daily friction, secure storage.

Feature: Authentication
  As Seth, the only user,
  I want to log in with my email and password and stay signed in on my phone,
  so my health data is protected without daily login hassle.

  Background:
    Given the app has a single account with my email and password

  Scenario: Logging in with the right credentials grants access
    When I log in with my correct email and password
    Then I reach the app

  Scenario: A wrong password is rejected
    When I log in with my email and the wrong password
    Then I am not let in
    And no data is shown

  Scenario: Protected data requires login
    Given I am not logged in
    When I try to open today's list
    Then I am asked to log in first

  Scenario: My session persists on my device
    Given I logged in on my phone
    When I reopen the app later that day
    Then I am still logged in

  Scenario: Logging out ends the session
    Given I am logged in
    When I log out
    Then I must log in again to get back in

  Scenario: An expired session requires re-authentication
    Given my session has expired
    When I open the app
    Then I am asked to log in again
