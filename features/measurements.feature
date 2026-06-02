# Behaviour spec — written before implementation (BDD-first). Declarative style.
# Body-composition tracking. Fields and units from the real vault:
# waist/tummy/bum/right_thigh/left_thigh in cm, weight in kg.

Feature: Body measurements
  As Seth, tracking body composition for my PT's check-ins,
  I want to record measurements and see how they're trending,
  so progress is visible and my check-in numbers are accurate.

  Background:
    Given I am logged in

  Scenario: Record a full set of measurements
    When I record measurements for 2026-05-25:
      | metric         | value |
      | waist_cm       | 96    |
      | tummy_cm       | 106   |
      | bum_cm         | 106   |
      | right_thigh_cm | 61    |
      | left_thigh_cm  | 62    |
      | weight_kg      | 94    |
    Then they are saved against 2026-05-25

  Scenario: Record only some metrics
    When I record only weight_kg 93 for 2026-05-26
    Then weight is saved for 2026-05-26
    And the other metrics are left blank for that date

  Scenario: See the change since the previous measurement
    Given I recorded waist_cm 98 on 2026-05-18
    When I record waist_cm 96 on 2026-05-25
    Then the 2026-05-25 entry shows a change of -2 cm on waist since the previous reading

  Scenario: See the trend for a metric over time
    Given I have several weeks of waist_cm measurements
    When I view the waist trend
    Then I see waist plotted over time

  Scenario: Edit a measurement
    Given I recorded weight_kg 94 on 2026-05-25
    When I correct it to 93.5
    Then the 2026-05-25 weight reads 93.5
    And no duplicate entry is created
