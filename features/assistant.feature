# Behaviour spec — the in-app assistant: a Claude (Opus) agent with read + write tools
# over Seth's data, on the Home screen. Tools run server-side, in-process. The same tool
# registry will also be exposed as an authed MCP server for external clients.

Feature: In-app assistant
  As Seth, I want to ask free-text questions about my data and make quick changes,
  so the hub is something I can interrogate and update conversationally.

  Background:
    Given I am logged in
    And the assistant is configured with an Anthropic API key

  Scenario: Ask about my data
    When I ask the assistant "how's my glucose this week?"
    Then it reads my glucose data and answers with my real average and time-in-range

  Scenario: Ask about exercise progress
    When I ask the assistant "how is my leg press progressing?"
    Then it reads my logged sets and answers with the trend over time

  Scenario: Make a change via the assistant
    When I tell the assistant "log 4 sets of leg press at 45kg, 15 reps today"
    Then the sets are recorded against today's session
    And it confirms exactly what it logged

  Scenario: Never invents data
    Given there is no glucose data for the period asked about
    When I ask the assistant about that period
    Then it says there is no data rather than inventing numbers

  Scenario: Assistant is disabled without an API key
    Given no Anthropic API key is configured
    When I send a message to the assistant
    Then I am told the assistant isn't configured
