from pi_agent.types import (
    AgentEndEvent,
    AgentStartEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    TurnStartEvent,
    user_message,
)
from pi_coding_agent.event_log import format_agent_event


def test_format_agent_event_sequence():
    events = [
        AgentStartEvent(),
        TurnStartEvent(),
        MessageEndEvent(message=user_message("hi")),
        ToolExecutionStartEvent(
            tool_call_id="t1",
            tool_name="read",
            args={"path": "x.txt"},
        ),
        AgentEndEvent(messages=[]),
    ]
    lines = [format_agent_event(event) for event in events]
    assert lines[0] == "agent_start"
    assert lines[1] == "turn_start"
    assert lines[2] == "message_end user"
    assert "tool_execution_start read" in lines[3]
    assert lines[4] == "agent_end messages=0"
