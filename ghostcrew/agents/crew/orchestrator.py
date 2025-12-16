"""Crew orchestrator - an agent that manages other agents."""

import json
import platform
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from ...config.constants import DEFAULT_MAX_ITERATIONS
from ...knowledge.graph import ShadowGraph
from ..prompts import ghost_crew
from .models import CrewState, WorkerCallback
from .tools import create_crew_tools
from .worker_pool import WorkerPool

if TYPE_CHECKING:
    from ...llm import LLM
    from ...runtime import Runtime
    from ...tools import Tool


class CrewOrchestrator:
    """Orchestrator that manages worker agents via tool calls."""

    def __init__(
        self,
        llm: "LLM",
        tools: List["Tool"],
        runtime: "Runtime",
        on_worker_event: Optional[WorkerCallback] = None,
        rag_engine: Any = None,
        target: str = "",
        prior_context: str = "",
    ):
        self.llm = llm
        self.base_tools = tools
        self.runtime = runtime
        self.on_worker_event = on_worker_event
        self.rag_engine = rag_engine
        self.target = target
        self.prior_context = prior_context

        self.state = CrewState.IDLE
        self.pool: Optional[WorkerPool] = None
        self.graph = ShadowGraph()
        self._messages: List[Dict[str, Any]] = []

    def _get_system_prompt(self) -> str:
        """Build the system prompt with target info and context."""
        tool_lines = []
        for t in self.base_tools:
            desc = (
                t.description[:80] + "..." if len(t.description) > 80 else t.description
            )
            tool_lines.append(f"- **{t.name}**: {desc}")
        worker_tools_formatted = (
            "\n".join(tool_lines) if tool_lines else "No tools available"
        )

        # Get saved notes if available
        notes_context = ""
        graph_insights = []
        try:
            from ...tools.notes import get_all_notes_sync

            notes = get_all_notes_sync()
            if notes:
                # Update shadow graph
                self.graph.update_from_notes(notes)
                graph_insights = self.graph.get_strategic_insights()

                # Group by category
                grouped = {}
                for key, data in notes.items():
                    # Handle legacy string format just in case
                    if isinstance(data, str):
                        cat = "info"
                        content = data
                    else:
                        cat = data.get("category", "info")
                        content = data.get("content", "")

                    # Truncate long notes in system prompt to save tokens
                    if len(content) > 200:
                        content = content[:197] + "..."

                    if cat not in grouped:
                        grouped[cat] = []
                    grouped[cat].append(f"- {key}: {content}")

                # Format output with specific order
                sections = []
                order = [
                    "credential",
                    "vulnerability",
                    "finding",
                    "artifact",
                    "task",
                    "info",
                ]

                for cat in order:
                    if cat in grouped:
                        header = cat.title() + "s"
                        if cat == "info":
                            header = "General Information"
                        sections.append(f"## {header}")
                        sections.append("\n".join(grouped[cat]))

                # Add any remaining categories
                for cat in sorted(grouped.keys()):
                    if cat not in order:
                        sections.append(f"## {cat.title()}")
                        sections.append("\n".join(grouped[cat]))

                notes_context = "\n\n".join(sections)
        except Exception:
            pass  # Notes not available

        # Format insights for prompt
        insights_text = ""
        if graph_insights:
            insights_text = "\n\n## Strategic Insights (Graph Analysis)\n" + "\n".join(
                f"- {i}" for i in graph_insights
            )

        return ghost_crew.render(
            target=self.target or "Not specified",
            prior_context=self.prior_context or "None - starting fresh",
            notes_context=notes_context + insights_text,
            worker_tools=worker_tools_formatted,
            environment={
                "os": platform.system(),
                "os_version": platform.release(),
                "architecture": platform.machine(),
            },
        )

    async def run(self, task: str) -> AsyncIterator[Dict[str, Any]]:
        """Run the crew on a task."""
        self.state = CrewState.RUNNING
        yield {"phase": "starting"}

        self.pool = WorkerPool(
            llm=self.llm,
            tools=self.base_tools,
            runtime=self.runtime,
            target=self.target,
            rag_engine=self.rag_engine,
            on_worker_event=self.on_worker_event,
        )

        crew_tools = create_crew_tools(self.pool, self.llm)

        self._messages = [
            {"role": "user", "content": f"Target: {self.target}\n\nTask: {task}"}
        ]

        iteration = 0
        final_report = ""

        try:
            while iteration < DEFAULT_MAX_ITERATIONS:
                iteration += 1

                response = await self.llm.generate(
                    system_prompt=self._get_system_prompt(),
                    messages=self._messages,
                    tools=crew_tools,
                )

                # Track tokens for orchestrator
                if response.usage:
                    total = response.usage.get("total_tokens", 0)
                    if total > 0:
                        yield {"phase": "tokens", "tokens": total}

                # Check for tool calls first to determine if content is "thinking" or "final answer"
                if response.tool_calls:
                    # If there are tool calls, the content is "thinking" (reasoning before action)
                    if response.content:
                        yield {"phase": "thinking", "content": response.content}
                        self._messages.append(
                            {"role": "assistant", "content": response.content}
                        )

                    def get_tc_name(tc):
                        if hasattr(tc, "function"):
                            return tc.function.name
                        return (
                            tc.get("function", {}).get("name", "")
                            if isinstance(tc, dict)
                            else ""
                        )

                    def get_tc_args(tc):
                        if hasattr(tc, "function"):
                            args = tc.function.arguments
                        else:
                            args = (
                                tc.get("function", {}).get("arguments", "{}")
                                if isinstance(tc, dict)
                                else "{}"
                            )
                        if isinstance(args, str):
                            try:
                                return json.loads(args)
                            except json.JSONDecodeError:
                                return {}
                        return args if isinstance(args, dict) else {}

                    def get_tc_id(tc):
                        if hasattr(tc, "id"):
                            return tc.id
                        return tc.get("id", "") if isinstance(tc, dict) else ""

                    self._messages.append(
                        {
                            "role": "assistant",
                            "content": response.content or "",
                            "tool_calls": [
                                {
                                    "id": get_tc_id(tc),
                                    "type": "function",
                                    "function": {
                                        "name": get_tc_name(tc),
                                        "arguments": json.dumps(get_tc_args(tc)),
                                    },
                                }
                                for tc in response.tool_calls
                            ],
                        }
                    )

                    for tc in response.tool_calls:
                        tc_name = get_tc_name(tc)
                        tc_args = get_tc_args(tc)
                        tc_id = get_tc_id(tc)

                        yield {"phase": "tool_call", "tool": tc_name, "args": tc_args}

                        tool = next((t for t in crew_tools if t.name == tc_name), None)
                        if tool:
                            try:
                                result = await tool.execute(tc_args, self.runtime)

                                yield {
                                    "phase": "tool_result",
                                    "tool": tc_name,
                                    "result": result,
                                }

                                self._messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "content": str(result),
                                    }
                                )

                                if tc_name == "synthesize_findings":
                                    final_report = result

                            except Exception as e:
                                error_msg = f"Error: {e}"
                                yield {
                                    "phase": "tool_result",
                                    "tool": tc_name,
                                    "result": error_msg,
                                }
                                self._messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tc_id,
                                        "content": error_msg,
                                    }
                                )
                        else:
                            error_msg = f"Unknown tool: {tc_name}"
                            self._messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "content": error_msg,
                                }
                            )

                    if final_report:
                        break
                else:
                    # No tool calls - the content IS the final report (Direct Answer)
                    content = response.content or ""
                    if content:
                        final_report = content
                        # Record it in history but don't yield as "thinking"
                        self._messages.append({"role": "assistant", "content": content})
                        break

            self.state = CrewState.COMPLETE
            yield {"phase": "complete", "report": final_report}

        except Exception as e:
            self.state = CrewState.ERROR
            yield {"phase": "error", "error": str(e)}

        finally:
            if self.pool:
                await self.pool.cancel_all()

    async def cancel(self) -> None:
        """Cancel the crew run."""
        if self.pool:
            await self.pool.cancel_all()
        self._cleanup_pending_calls()
        self.state = CrewState.IDLE

    def _cleanup_pending_calls(self) -> None:
        """Remove incomplete tool calls from message history."""
        while self._messages:
            last_msg = self._messages[-1]
            if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                self._messages.pop()
            elif last_msg.get("role") == "tool":
                self._messages.pop()
            elif last_msg.get("role") == "user":
                self._messages.pop()
                break
            else:
                break
