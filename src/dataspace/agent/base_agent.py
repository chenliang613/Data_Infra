"""Base Claude Connector Agent with agentic tool-use loop."""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

import anthropic

MODEL = "claude-sonnet-4-6"


class AgentTurnResult:
    """Result of a single agent turn."""
    def __init__(
        self,
        text: str,
        tool_name: Optional[str] = None,
        tool_input: Optional[dict] = None,
        stop_reason: str = "end_turn",
    ):
        self.text = text
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.stop_reason = stop_reason

    @property
    def accepted(self) -> bool:
        return self.tool_name == "accept_contract"

    @property
    def rejected(self) -> bool:
        return self.tool_name == "reject_negotiation"

    @property
    def counter_proposed(self) -> bool:
        return self.tool_name == "counter_propose"


class BaseConnectorAgent:
    """
    Claude-powered connector agent.
    Manages conversation history and executes one turn at a time.
    """

    def __init__(
        self,
        system_prompt: str,
        tools: List[dict],
        tool_handlers: Dict[str, Callable[[dict], str]],
    ):
        self.client = anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.conversation: List[dict] = []

    def reset(self) -> None:
        self.conversation = []

    def _build_tool_result(self, tool_use_id: str, content: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
        }

    def respond(self, incoming_message: str) -> AgentTurnResult:
        """
        Process an incoming message and return the agent's response.
        Runs the internal agentic loop until a final text response or
        a terminal tool call (accept/reject/counter).
        """
        # Add incoming message to conversation
        self.conversation.append({"role": "user", "content": incoming_message})

        last_text = ""
        terminal_tool_name: Optional[str] = None
        terminal_tool_input: Optional[dict] = None

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=self.system_prompt,
                tools=self.tools,
                messages=self.conversation,
            )

            # Collect text and tool_use blocks
            assistant_content = []
            text_parts = []
            tool_uses = []

            for block in response.content:
                assistant_content.append(block)
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            last_text = " ".join(text_parts)

            # Append assistant message to history
            self.conversation.append({
                "role": "assistant",
                "content": response.content,
            })

            # If terminal tool was called, stop immediately
            terminal_names = {"accept_contract", "reject_negotiation"}
            terminal_tool_blocks = [t for t in tool_uses if t.name in terminal_names]
            if terminal_tool_blocks:
                tb = terminal_tool_blocks[0]
                terminal_tool_name = tb.name
                terminal_tool_input = tb.input
                # Execute handler if registered
                if tb.name in self.tool_handlers:
                    result_str = self.tool_handlers[tb.name](tb.input)
                    self.conversation.append({
                        "role": "user",
                        "content": [self._build_tool_result(tb.id, result_str)],
                    })
                break

            # Handle counter_propose as semi-terminal (return to caller for routing)
            counter_tools = [t for t in tool_uses if t.name == "counter_propose"]
            if counter_tools:
                ct = counter_tools[0]
                result_str = "反提案已记录，等待对方回应。"
                if ct.name in self.tool_handlers:
                    result_str = self.tool_handlers[ct.name](ct.input)
                self.conversation.append({
                    "role": "user",
                    "content": [self._build_tool_result(ct.id, result_str)],
                })
                return AgentTurnResult(
                    text=ct.input.get("explanation", last_text),
                    tool_name="counter_propose",
                    tool_input=ct.input,
                    stop_reason="tool_use",
                )

            # Handle non-terminal tools (review_catalog, check_policy, describe_need)
            if tool_uses and not terminal_tool_blocks:
                tool_results = []
                for tu in tool_uses:
                    if tu.name in self.tool_handlers:
                        result_str = self.tool_handlers[tu.name](tu.input)
                    else:
                        result_str = json.dumps({"error": f"No handler for '{tu.name}'"})
                    tool_results.append(self._build_tool_result(tu.id, result_str))
                self.conversation.append({"role": "user", "content": tool_results})
                continue  # Continue agentic loop

            # No more tool calls — natural end_turn
            break

        return AgentTurnResult(
            text=last_text,
            tool_name=terminal_tool_name,
            tool_input=terminal_tool_input,
            stop_reason=response.stop_reason,
        )
