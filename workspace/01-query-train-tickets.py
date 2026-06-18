"""Chapter 01 exercise: define a tool contract for a personal assistant."""

import json
import inspect
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator


class QueryTrainTicketsArgs(BaseModel):
    """The arguments accepted by the train-ticket query tool."""

    origin: str = Field(description="出发车站的完整名称，例如：北京南")
    destination: str = Field(description="到达车站的完整名称，例如：上海虹桥")
    travel_date: date = Field(description="乘车日期，格式为 YYYY-MM-DD")

    @model_validator(mode="after")
    def validate_query(self):
        if self.origin.strip() == self.destination.strip():
            raise ValueError("出发站和到达站不能相同")
        if self.travel_date < date.today():
            raise ValueError("乘车日期不能早于今天")
        return self


QUERY_TRAIN_TICKETS_TOOL = {
    "name": "query_train_tickets",
    "description": (
        "查询指定出发站、到达站和乘车日期的实时火车班次及余票。"
        "当用户明确询问火车班次或余票，或者制定出差计划且需要实时火车数据时使用。"
        "不要用于购买、退票、改签、查询历史班次，也不要在只需要普通旅行建议时使用。"
        "返回匹配的车次、出发时间、到达时间和各席别余票。"
    ),
    "input_schema": QueryTrainTicketsArgs.model_json_schema(),
}


# A protocol-neutral example of the exact JSON emitted by the model.
EXAMPLE_MODEL_TOOL_REQUEST = {
    "id": "call_train_001",
    "name": "query_train_tickets",
    "input": {
        "origin": "北京南",
        "destination": "上海虹桥",
        "travel_date": "2026-06-25",
    },
}


def query_train_tickets(
    departure_station: str,
    destination: str,
    travel_date: str,
) -> dict[str, Any]:
    """Deliberately drifted handler: `origin` was renamed only here."""

    return {
        "origin": departure_station,
        "destination": destination,
        "travel_date": travel_date,
        "trains": [],
    }


TOOL_HANDLERS = {"query_train_tickets": query_train_tickets}


def dispatch_tool_call_before(
    request: dict[str, Any],
    handlers: dict[str, Any] = None,
) -> dict[str, Any]:
    """Before: exceptions escape and can terminate the agent loop."""

    handlers = TOOL_HANDLERS if handlers is None else handlers
    handler = handlers[request["name"]]
    validated_args = QueryTrainTicketsArgs.model_validate(request["input"])
    handler_args = validated_args.model_dump(mode="json")
    return {
        "tool_call_id": request["id"],
        "ok": True,
        "result": handler(**handler_args),
    }


def _validation_error_message(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors(include_url=False):
        field = ".".join(str(part) for part in error["loc"])
        problems.append(f"{field}: {error['msg']}")
    return "Invalid tool arguments: " + "; ".join(problems)


def _error_tool_result(
    call_id: str,
    exc: Exception,
    stage: str,
    handler: Any = None,
    handler_args: dict[str, Any] = None,
) -> dict[str, Any]:
    """Classify an exception into a model-readable error envelope."""

    error_type = type(exc).__name__

    if isinstance(exc, ValidationError):
        code = "INVALID_ARGUMENTS"
        message = _validation_error_message(exc)
        retryable = True
    elif isinstance(exc, (TimeoutError, ConnectionError)):
        code = "TRANSIENT_TOOL_ERROR"
        message = str(exc) or "The tool temporarily failed."
        retryable = True
    elif stage == "lookup" and isinstance(exc, KeyError):
        code = "UNKNOWN_TOOL"
        message = f"Unknown tool: {exc.args[0]}"
        retryable = False
    elif stage == "execution" and isinstance(exc, TypeError) and handler:
        accepted_fields = inspect.signature(handler).parameters
        unexpected_field = next(
            (
                field
                for field in (handler_args or {})
                if field not in accepted_fields
            ),
            None,
        )
        if unexpected_field:
            code = "TOOL_CONTRACT_ERROR"
            message = (
                f"{handler.__name__} does not accept schema field "
                f"'{unexpected_field}'."
            )
        else:
            code = "TOOL_EXECUTION_ERROR"
            message = "Tool execution failed."
        retryable = False
    else:
        code = "TOOL_EXECUTION_ERROR"
        message = "Tool execution failed."
        retryable = False

    return {
        "tool_call_id": call_id,
        "ok": False,
        "error": {
            "code": code,
            "type": error_type,
            "message": message,
            "retryable": retryable,
        },
    }


def dispatch_tool_call(
    request: dict[str, Any],
    handlers: dict[str, Any] = None,
) -> dict[str, Any]:
    """After: every ordinary exception becomes a readable tool result."""

    handlers = TOOL_HANDLERS if handlers is None else handlers
    call_id = request.get("id", "unknown")
    stage = "lookup"
    handler = None
    handler_args = None

    try:
        handler = handlers[request["name"]]
        stage = "validation"
        validated_args = QueryTrainTicketsArgs.model_validate(request["input"])
        handler_args = validated_args.model_dump(mode="json")
        stage = "execution"
        return {
            "tool_call_id": call_id,
            "ok": True,
            "result": handler(**handler_args),
        }
    except Exception as exc:
        # This is the agent-loop boundary. Catch Exception, not BaseException:
        # KeyboardInterrupt and SystemExit must still stop the process.
        return _error_tool_result(
            call_id=call_id,
            exc=exc,
            stage=stage,
            handler=handler,
            handler_args=handler_args,
        )


if __name__ == "__main__":
    print("Tool definition:")
    print(json.dumps(QUERY_TRAIN_TICKETS_TOOL, ensure_ascii=False, indent=2))
    print("\nModel tool request:")
    print(json.dumps(EXAMPLE_MODEL_TOOL_REQUEST, ensure_ascii=False, indent=2))

    print("\nBefore wrapping (exception escapes):")
    try:
        dispatch_tool_call_before(EXAMPLE_MODEL_TOOL_REQUEST)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")

    print("\nAfter wrapping (exception becomes tool_result):")
    tool_result = dispatch_tool_call(EXAMPLE_MODEL_TOOL_REQUEST)
    print(json.dumps(tool_result, ensure_ascii=False, indent=2))

    def timeout_handler(**_kwargs):
        raise TimeoutError("ticket provider timed out")

    print("\nRetryable timeout tool_result:")
    timeout_result = dispatch_tool_call(
        EXAMPLE_MODEL_TOOL_REQUEST,
        handlers={"query_train_tickets": timeout_handler},
    )
    print(json.dumps(timeout_result, ensure_ascii=False, indent=2))
