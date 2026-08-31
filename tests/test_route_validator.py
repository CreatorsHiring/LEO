import unittest

from backend.app.models import Domain, RouteDecision
from backend.app.route_validator import (
    RouteValidator,
    heuristic_fallback_domain,
    strongest_signal_domain,
)


class RouteValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = RouteValidator()

    def _validate_prompt(self, prompt: str, expected: Domain) -> None:
        signal_domain = strongest_signal_domain(prompt)
        self.assertEqual(
            heuristic_fallback_domain(prompt),
            expected,
            f"heuristic fallback mismatch for: {prompt}",
        )
        if signal_domain is not None:
            bad_decision = RouteDecision(
                domain=Domain.general,
                confidence=1.0,
                rationale="General informational request.",
                needs_retrieval=False,
            )
            validated = self.validator.validate(bad_decision, prompt)
            self.assertEqual(
                validated.domain,
                expected,
                f"validator did not override bad router output for: {prompt}",
            )

    def test_java_hello_world(self) -> None:
        self._validate_prompt("write a java code for hello world", Domain.code)

    def test_python_reverse_string(self) -> None:
        self._validate_prompt("write a Python function to reverse a string", Domain.code)

    def test_debug_java_program(self) -> None:
        self._validate_prompt("debug this Java program", Domain.code)

    def test_design_rest_api(self) -> None:
        self._validate_prompt("design a REST API", Domain.code)

    def test_calculate_percentage(self) -> None:
        self._validate_prompt("calculate 25% of 800", Domain.math)

    def test_solve_integral(self) -> None:
        self._validate_prompt("solve this integral", Domain.math)

    def test_primary_key_general(self) -> None:
        decision = RouteDecision(
            domain=Domain.general,
            confidence=0.9,
            rationale="The user wants a database concept explained.",
            needs_retrieval=False,
        )
        validated = self.validator.validate(decision, "what is a primary key?")
        self.assertEqual(validated.domain, Domain.general)

    def test_summarize_company_policy(self) -> None:
        decision = RouteDecision(
            domain=Domain.general,
            confidence=0.9,
            rationale="The user wants a business document summarized.",
            needs_retrieval=True,
        )
        validated = self.validator.validate(decision, "summarize this company policy")
        self.assertEqual(validated.domain, Domain.general)

    def test_diabetes_symptoms_medical(self) -> None:
        self._validate_prompt("what are symptoms of diabetes?", Domain.medical)

    def test_contradictory_router_output_corrected_to_code(self) -> None:
        bad_decision = RouteDecision(
            domain=Domain.general,
            confidence=1.0,
            rationale="The user wants Java code.",
            needs_retrieval=False,
        )
        validated = self.validator.validate(bad_decision, "write a java code for hello world")
        self.assertEqual(validated.domain, Domain.code)


if __name__ == "__main__":
    unittest.main()
