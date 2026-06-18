"""Tests for the Chapter 01 tool-error wrapping exercise."""

import copy
import runpy
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("01-query-train-tickets.py")


class SchemaDriftExerciseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = runpy.run_path(str(SCRIPT))

    def test_before_wrapper_schema_drift_escapes_as_type_error(self):
        self.assertIn("dispatch_tool_call_before", self.module)
        before_dispatch = self.module["dispatch_tool_call_before"]

        with self.assertRaisesRegex(
            TypeError, "unexpected keyword argument 'origin'"
        ):
            before_dispatch(self.module["EXAMPLE_MODEL_TOOL_REQUEST"])

    def test_after_wrapper_schema_drift_becomes_permanent_tool_error(self):
        schema = self.module["QUERY_TRAIN_TICKETS_TOOL"]["input_schema"]
        request = self.module["EXAMPLE_MODEL_TOOL_REQUEST"]
        dispatch = self.module["dispatch_tool_call"]

        self.assertIn("origin", schema["properties"])
        self.assertNotIn("departure_station", schema["properties"])

        self.assertEqual(
            dispatch(request),
            {
                "tool_call_id": "call_train_001",
                "ok": False,
                "error": {
                    "code": "TOOL_CONTRACT_ERROR",
                    "type": "TypeError",
                    "message": (
                        "query_train_tickets does not accept schema field "
                        "'origin'."
                    ),
                    "retryable": False,
                },
            },
        )

    def test_timeout_becomes_retryable_tool_error(self):
        def timeout_handler(**_kwargs):
            raise TimeoutError("ticket provider timed out")

        result = self.dispatch_without_leaking(
            handlers={"query_train_tickets": timeout_handler}
        )

        self.assertEqual(result["tool_call_id"], "call_train_001")
        self.assertEqual(result["error"]["code"], "TRANSIENT_TOOL_ERROR")
        self.assertEqual(result["error"]["type"], "TimeoutError")
        self.assertEqual(result["error"]["message"], "ticket provider timed out")
        self.assertTrue(result["error"]["retryable"])

    def test_unknown_runtime_exception_becomes_non_retryable_tool_error(self):
        def broken_handler(**_kwargs):
            raise RuntimeError("database exploded")

        result = self.dispatch_without_leaking(
            handlers={"query_train_tickets": broken_handler}
        )

        self.assertEqual(result["error"]["code"], "TOOL_EXECUTION_ERROR")
        self.assertEqual(result["error"]["type"], "RuntimeError")
        self.assertEqual(result["error"]["message"], "Tool execution failed.")
        self.assertFalse(result["error"]["retryable"])

    def test_validation_exception_becomes_correctable_tool_error(self):
        request = copy.deepcopy(self.module["EXAMPLE_MODEL_TOOL_REQUEST"])
        request["input"]["travel_date"] = "not-a-date"

        result = self.dispatch_without_leaking(request=request)

        self.assertEqual(result["error"]["code"], "INVALID_ARGUMENTS")
        self.assertEqual(result["error"]["type"], "ValidationError")
        self.assertIn("travel_date", result["error"]["message"])
        self.assertTrue(result["error"]["retryable"])

    def dispatch_without_leaking(self, request=None, handlers=None):
        request = request or self.module["EXAMPLE_MODEL_TOOL_REQUEST"]
        kwargs = {} if handlers is None else {"handlers": handlers}
        try:
            return self.module["dispatch_tool_call"](request, **kwargs)
        except Exception as exc:
            self.fail(
                "wrapped dispatcher leaked "
                f"{type(exc).__name__}: {exc}"
            )


if __name__ == "__main__":
    unittest.main()
