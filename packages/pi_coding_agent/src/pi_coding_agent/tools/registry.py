"""Built-in coding tools registry."""

from __future__ import annotations

from pi_agent.types import AgentTool

from pi_coding_agent.tools.bash import create_bash_tool
from pi_coding_agent.tools.read import create_read_tool

ToolName = str


def create_coding_tools(cwd: str) -> list[AgentTool]:
    return [create_read_tool(cwd), create_bash_tool(cwd)]


def create_tools_for_names(cwd: str, names: list[str]) -> list[AgentTool]:
    all_tools = {tool.name: tool for tool in create_coding_tools(cwd)}
    tools: list[AgentTool] = []
    for name in names:
        tool = all_tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        tools.append(tool)
    return tools
