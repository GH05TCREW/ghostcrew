"""Tool executor for PentestAgent."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..runtime import Runtime
    from .registry import Tool


@dataclass
class ExecutionResult:
    """Result of a tool execution."""

    tool_name: str
    arguments: dict
    result: Optional[str] = None
    error: Optional[str] = None
    success: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0

    @property
    def duration(self) -> float:
        """Get execution duration in seconds."""
        return self.duration_ms / 1000.0


class ToolExecutor:
    """Handles tool execution with error handling and logging."""

    def __init__(self, runtime: "Runtime", timeout: int = 300, max_retries: int = 0):
        """
        Initialize the tool executor.

        Args:
            runtime: The runtime environment
            timeout: Default timeout for tool execution in seconds
            max_retries: Number of retries on failure
        """
        self.runtime = runtime
        self.timeout = timeout
        self.max_retries = max_retries
        self.execution_history: List[ExecutionResult] = []

    async def execute(
        self, tool: "Tool", arguments: dict, timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a tool with the given arguments.

        Args:
            tool: The tool to execute
            arguments: The arguments to pass to the tool
            timeout: Optional timeout override

        Returns:
            ExecutionResult with the outcome
        """
        execution_timeout = timeout or self.timeout
        start_time = datetime.now()

        # Validate arguments
        is_valid, error_msg = tool.validate_arguments(arguments)
        if not is_valid:
            result = ExecutionResult(
                tool_name=tool.name,
                arguments=arguments,
                error=error_msg,
                success=False,
                start_time=start_time,
                end_time=datetime.now(),
            )
            result.duration_ms = (result.end_time - start_time).total_seconds() * 1000
            self.execution_history.append(result)
            return result

        # Execute with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Execute with timeout
                output = await asyncio.wait_for(
                    tool.execute(arguments, self.runtime), timeout=execution_timeout
                )

                end_time = datetime.now()
                result = ExecutionResult(
                    tool_name=tool.name,
                    arguments=arguments,
                    result=output,
                    success=True,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time).total_seconds() * 1000,
                )
                self.execution_history.append(result)
                return result

            except asyncio.TimeoutError:
                last_error = f"Execution timed out after {execution_timeout} seconds"
            except Exception as e:
                last_error = str(e)

            # Wait before retry
            if attempt < self.max_retries:
                await asyncio.sleep(1)

        # All attempts failed
        end_time = datetime.now()
        result = ExecutionResult(
            tool_name=tool.name,
            arguments=arguments,
            error=last_error,
            success=False,
            start_time=start_time,
            end_time=end_time,
            duration_ms=(end_time - start_time).total_seconds() * 1000,
        )
        self.execution_history.append(result)
        return result

    async def execute_batch(
        self, executions: List[tuple["Tool", dict]], parallel: bool = False
    ) -> List[ExecutionResult]:
        """
        Execute multiple tools.

        Args:
            executions: List of (tool, arguments) tuples
            parallel: Whether to execute in parallel

        Returns:
            List of ExecutionResults
        """
        if parallel:
            tasks = [self.execute(tool, args) for tool, args in executions]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for tool, args in executions:
                result = await self.execute(tool, args)
                results.append(result)
            return results

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tool executions.

        Returns:
            Dictionary with execution statistics
        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "tools_used": {},
            }

        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        failed = total - successful

        # Calculate average duration
        durations = [r.duration_ms for r in self.execution_history]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Count tool usage
        tools_used: Dict[str, int] = {}
        for result in self.execution_history:
            tools_used[result.tool_name] = tools_used.get(result.tool_name, 0) + 1

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration_ms": avg_duration,
            "tools_used": tools_used,
        }

    def clear_history(self):
        """Clear the execution history."""
        self.execution_history.clear()

    def get_last_result(
        self, tool_name: Optional[str] = None
    ) -> Optional[ExecutionResult]:
        """
        Get the last execution result.

        Args:
            tool_name: Optional filter by tool name

        Returns:
            The last ExecutionResult or None
        """
        if not self.execution_history:
            return None

        if tool_name:
            for result in reversed(self.execution_history):
                if result.tool_name == tool_name:
                    return result
            return None

        return self.execution_history[-1]
