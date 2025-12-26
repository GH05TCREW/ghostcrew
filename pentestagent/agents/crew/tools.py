"""Orchestration tools for the crew agent."""

import json
from typing import TYPE_CHECKING, List

from ...tools.registry import Tool, ToolSchema

if TYPE_CHECKING:
    from ...llm import LLM
    from ...runtime import Runtime
    from .worker_pool import WorkerPool


def create_crew_tools(pool: "WorkerPool", llm: "LLM") -> List[Tool]:
    """Create orchestration tools bound to a worker pool."""

    async def spawn_agent_fn(arguments: dict, runtime: "Runtime") -> str:
        """Spawn a new agent to work on a task."""
        task = arguments.get("task", "")
        priority = arguments.get("priority", 1)
        depends_on = arguments.get("depends_on", [])

        if not task:
            return "Error: task is required"

        agent_id = await pool.spawn(task, priority, depends_on)
        return f"Spawned {agent_id}: {task}"

    async def wait_for_agents_fn(arguments: dict, runtime: "Runtime") -> str:
        """Wait for agents to complete and get their results."""
        agent_ids = arguments.get("agent_ids", None)

        results = await pool.wait_for(agent_ids)

        if not results:
            return "No agents to wait for."

        output = []
        for agent_id, data in results.items():
            status = data.get("status", "unknown")
            task = data.get("task", "")
            result = data.get("result", "")
            error = data.get("error", "")
            tools = data.get("tools_used", [])

            output.append(f"## {agent_id}: {task}")
            output.append(f"Status: {status}")
            if tools:
                output.append(f"Tools used: {', '.join(tools)}")
            if result:
                output.append(f"Result:\n{result}")
            if error:
                output.append(f"Error: {error}")
            output.append("")

        return "\n".join(output)

    async def get_agent_status_fn(arguments: dict, runtime: "Runtime") -> str:
        """Check the current status of an agent."""
        agent_id = arguments.get("agent_id", "")

        if not agent_id:
            return "Error: agent_id is required"

        status = pool.get_status(agent_id)
        if not status:
            return f"Agent {agent_id} not found."

        return json.dumps(status, indent=2)

    async def cancel_agent_fn(arguments: dict, runtime: "Runtime") -> str:
        """Cancel a running agent."""
        agent_id = arguments.get("agent_id", "")

        if not agent_id:
            return "Error: agent_id is required"

        success = await pool.cancel(agent_id)
        if success:
            return f"Cancelled {agent_id}"
        return f"Could not cancel {agent_id} (not running or not found)"

    async def finish_fn(arguments: dict, runtime: "Runtime") -> str:
        """Finish crew task: wait for agents, synthesize results, return final summary."""
        context = arguments.get("context", "")

        # Step 1: Wait for all agents to complete
        await pool.wait_for(None)

        # Step 2: Gather agent results
        workers = pool.get_workers()
        if not workers:
            return context or "Task completed. No agents were spawned."

        results_text = []
        for w in workers:
            if w.result:
                results_text.append(f"## {w.id}: {w.task}\n{w.result}")
            elif w.error:
                results_text.append(f"## {w.id}: {w.task}\nError: {w.error}")

        if not results_text:
            return context or "Task completed. Agents ran but produced no results."

        # Step 3: Use LLM to synthesize findings into final summary
        prompt = f"""Synthesize these agent findings into a clear, concise summary.

Context: {context or 'Penetration test task completed.'}

Agent Results:
{chr(10).join(results_text)}

Provide a unified summary of what was accomplished and key findings."""

        response = await llm.generate(
            system_prompt="You are synthesizing penetration test results. Be factual, clear, and concise.",
            messages=[{"role": "user", "content": prompt}],
            tools=[],
        )

        # Store token usage for orchestrator to report
        if response.usage:
            pool.finish_tokens = response.usage.get("total_tokens", 0)

        return response.content

    async def formulate_strategy_fn(arguments: dict, runtime: "Runtime") -> str:
        """Formulate and select a strategic Course of Action (COA)."""
        problem = arguments.get("problem", "")
        candidates = arguments.get("candidates", [])
        selected_id = arguments.get("selected_id", "")
        rationale = arguments.get("rationale", "")
        feasible = arguments.get("feasible", True)

        if not problem:
            return "Error: problem is required."

        if not feasible:
            return f"## Strategic Decision: TERMINATE MISSION\n**Problem:** {problem}\n**Rationale:** {rationale}\n\nMission marked as infeasible."

        if not candidates or not selected_id:
            return "Error: candidates and selected_id are required when feasible=True."

        # Find selected candidate
        selected = next((c for c in candidates if c.get("id") == selected_id), None)
        if not selected:
            return f"Error: Selected ID '{selected_id}' not found in candidates."

        # Format the decision for the log/history
        output = [
            f"## Strategic Decision: {selected.get('name', 'Unknown')}",
            f"**Problem:** {problem}",
            "",
            "**Considered Options:**",
        ]

        for c in candidates:
            mark = "(SELECTED)" if c.get("id") == selected_id else ""
            output.append(f"- **{c.get('name')}** {mark}")
            output.append(f"  - Pros: {c.get('pros')}")
            output.append(f"  - Cons: {c.get('cons')}")
            output.append(f"  - Risk: {c.get('risk')}")

        output.append("")
        output.append(f"**Rationale:** {rationale}")

        return "\n".join(output)

    # Create Tool objects
    tools = [
        Tool(
            name="spawn_agent",
            description="Spawn a new agent to work on a specific task. Use for delegating work like port scanning, service enumeration, or vulnerability testing. Each agent runs independently with access to all pentest tools.",
            schema=ToolSchema(
                type="object",
                properties={
                    "task": {
                        "type": "string",
                        "description": "Clear, action-oriented task description. Be specific about what to scan/test and the target.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Execution priority (higher = runs sooner). Default 1.",
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Agent IDs that must complete before this agent starts. Use for sequential workflows.",
                    },
                },
                required=["task"],
            ),
            execute_fn=spawn_agent_fn,
            category="orchestration",
        ),
        Tool(
            name="wait_for_agents",
            description="Wait for spawned agents to complete and retrieve their results. Call this after spawning agents to get findings before proceeding.",
            schema=ToolSchema(
                type="object",
                properties={
                    "agent_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of agent IDs to wait for. Omit to wait for all spawned agents.",
                    }
                },
                required=[],
            ),
            execute_fn=wait_for_agents_fn,
            category="orchestration",
        ),
        Tool(
            name="get_agent_status",
            description="Check the current status of a specific agent. Useful for monitoring long-running tasks.",
            schema=ToolSchema(
                type="object",
                properties={
                    "agent_id": {
                        "type": "string",
                        "description": "The agent ID to check (e.g., 'agent-0')",
                    }
                },
                required=["agent_id"],
            ),
            execute_fn=get_agent_status_fn,
            category="orchestration",
        ),
        Tool(
            name="cancel_agent",
            description="Cancel a running agent. Use if an agent is taking too long or is no longer needed.",
            schema=ToolSchema(
                type="object",
                properties={
                    "agent_id": {
                        "type": "string",
                        "description": "The agent ID to cancel (e.g., 'agent-0')",
                    }
                },
                required=["agent_id"],
            ),
            execute_fn=cancel_agent_fn,
            category="orchestration",
        ),
        Tool(
            name="finish",
            description="Complete the crew task. Automatically waits for all agents, synthesizes their results using LLM, and returns final summary. Call this when task objectives are met.",
            schema=ToolSchema(
                type="object",
                properties={
                    "context": {
                        "type": "string",
                        "description": "Optional context about the task for synthesis (e.g., 'Tested SSH access on localhost'). Helps frame the summary.",
                    }
                },
                required=[],
            ),
            execute_fn=finish_fn,
            category="orchestration",
        ),
        Tool(
            name="formulate_strategy",
            description="Define and select a strategic Course of Action (COA). Use this when facing a strategic blocker or choosing an initial approach. This logs the decision process. Set feasible=False to terminate if no options exist.",
            schema=ToolSchema(
                type="object",
                properties={
                    "problem": {
                        "type": "string",
                        "description": "The strategic problem or blocker encountered.",
                    },
                    "feasible": {
                        "type": "boolean",
                        "description": "Whether a feasible solution exists. Set to False to terminate the mission.",
                        "default": True,
                    },
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "pros": {"type": "string"},
                                "cons": {"type": "string"},
                                "risk": {
                                    "type": "string",
                                    "enum": ["Low", "Medium", "High", "Critical"],
                                },
                            },
                            "required": ["id", "name", "pros", "cons", "risk"],
                        },
                        "description": "List of potential Courses of Action (COAs). Required if feasible=True.",
                    },
                    "selected_id": {
                        "type": "string",
                        "description": "The ID of the selected COA. Required if feasible=True.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this COA was selected over others (or why mission is infeasible).",
                    },
                },
                required=["problem", "rationale"],
            ),
            execute_fn=formulate_strategy_fn,
            category="orchestration",
        ),
    ]

    return tools
