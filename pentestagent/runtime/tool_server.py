"""Tool server for running tools in the sandbox."""

import asyncio
import json
from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class ToolRequest:
    """A tool execution request."""

    tool_name: str
    arguments: dict
    request_id: str


@dataclass
class ToolResponse:
    """A tool execution response."""

    request_id: str
    result: Optional[str] = None
    error: Optional[str] = None
    success: bool = True


class ToolServer:
    """
    Server that runs inside the sandbox to handle tool requests.

    This is used for more complex tool orchestration where
    tools need to run inside the container.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9999):
        """
        Initialize the tool server.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self._tools: Dict[str, Callable] = {}
        self._server = None
        self._running = False

    def register_tool(self, name: str, handler: Callable):
        """
        Register a tool handler.

        Args:
            name: Tool name
            handler: Async function to handle the tool
        """
        self._tools[name] = handler

    async def start(self):
        """Start the tool server."""
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        self._running = True

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        """Stop the tool server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle an incoming connection."""
        try:
            while self._running:
                # Read request
                data = await reader.readline()
                if not data:
                    break

                try:
                    request_data = json.loads(data.decode())
                    request = ToolRequest(
                        tool_name=request_data["tool"],
                        arguments=request_data.get("arguments", {}),
                        request_id=request_data.get("id", "unknown"),
                    )

                    # Execute tool
                    response = await self._execute_tool(request)

                    # Send response
                    response_data = {
                        "id": response.request_id,
                        "result": response.result,
                        "error": response.error,
                        "success": response.success,
                    }
                    writer.write((json.dumps(response_data) + "\n").encode())
                    await writer.drain()

                except json.JSONDecodeError:
                    error_response = {"error": "Invalid JSON", "success": False}
                    writer.write((json.dumps(error_response) + "\n").encode())
                    await writer.drain()

        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _execute_tool(self, request: ToolRequest) -> ToolResponse:
        """Execute a tool request."""
        handler = self._tools.get(request.tool_name)

        if not handler:
            return ToolResponse(
                request_id=request.request_id,
                error=f"Tool '{request.tool_name}' not found",
                success=False,
            )

        try:
            result = await handler(request.arguments)
            return ToolResponse(
                request_id=request.request_id, result=str(result), success=True
            )
        except Exception as e:
            return ToolResponse(
                request_id=request.request_id, error=str(e), success=False
            )


class ToolClient:
    """Client for communicating with the tool server in the sandbox."""

    def __init__(self, host: str = "localhost", port: int = 9999):
        """
        Initialize the tool client.

        Args:
            host: Tool server host
            port: Tool server port
        """
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0

    async def connect(self):
        """Connect to the tool server."""
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)

    async def disconnect(self):
        """Disconnect from the tool server."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def call_tool(self, tool_name: str, arguments: dict) -> ToolResponse:
        """
        Call a tool on the server.

        Args:
            tool_name: The tool to call
            arguments: Tool arguments

        Returns:
            ToolResponse with result
        """
        if not self._writer or not self._reader:
            raise RuntimeError("Not connected to tool server")

        self._request_id += 1
        request_id = str(self._request_id)

        # Send request
        request = {"id": request_id, "tool": tool_name, "arguments": arguments}
        self._writer.write((json.dumps(request) + "\n").encode())
        await self._writer.drain()

        # Read response
        response_data = await self._reader.readline()
        response = json.loads(response_data.decode())

        return ToolResponse(
            request_id=response.get("id", request_id),
            result=response.get("result"),
            error=response.get("error"),
            success=response.get("success", False),
        )
