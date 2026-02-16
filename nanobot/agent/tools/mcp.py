"""MCP (Model Context Protocol) tool adapter and lifecycle manager."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool


class MCPTool(Tool):
    """Wrap a single MCP server tool as a nanobot Tool."""

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        session: Any,
    ):
        self._server_name = server_name
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._input_schema = input_schema
        self._session = session

    @property
    def name(self) -> str:
        return f"mcp__{self._server_name}__{self._tool_name}"

    @property
    def description(self) -> str:
        return f"[MCP:{self._server_name}] {self._tool_description}"

    @property
    def parameters(self) -> dict[str, Any]:
        return self._input_schema

    async def execute(self, **kwargs: Any) -> str:
        try:
            result = await self._session.call_tool(self._tool_name, arguments=kwargs)
            parts: list[str] = []
            for item in result.content:
                text = getattr(item, "text", None)
                parts.append(text if isinstance(text, str) else str(item))
            return "\n".join(parts) if parts else "(empty result)"
        except Exception as e:
            return f"MCP Error ({self._server_name}/{self._tool_name}): {e}"


class _ServerHandle:
    """Holds runtime state for one MCP server connection."""

    def __init__(self, name: str):
        self.name = name
        self.task: asyncio.Task[None] | None = None
        self.session: Any = None
        self.tools: list[MCPTool] = []
        self.stop_event = asyncio.Event()


class MCPManager:
    """Manage lifecycle of MCP server connections."""

    def __init__(self, servers: dict[str, Any]):
        from nanobot.config.schema import McpServerConfig

        self._configs: dict[str, McpServerConfig] = {}
        for name, cfg in servers.items():
            if isinstance(cfg, McpServerConfig):
                if cfg.enabled:
                    self._configs[name] = cfg
            elif isinstance(cfg, dict):
                sc = McpServerConfig(**cfg)
                if sc.enabled:
                    self._configs[name] = sc
            else:
                if getattr(cfg, "enabled", True):
                    self._configs[name] = cfg

        self._handles: list[_ServerHandle] = []

    @property
    def server_names(self) -> list[str]:
        return [h.name for h in self._handles]

    async def start(self) -> list[MCPTool]:
        """Connect all configured MCP servers and return discovered tools."""
        all_tools: list[MCPTool] = []
        loop = asyncio.get_running_loop()

        for name, cfg in self._configs.items():
            handle = _ServerHandle(name)
            ready: asyncio.Future[None] = loop.create_future()
            handle.task = asyncio.create_task(self._run_server(name, cfg, handle, ready))

            try:
                await asyncio.wait_for(ready, timeout=30)
                self._handles.append(handle)
                all_tools.extend(handle.tools)
                logger.info("MCP server '{}': {} tools discovered", name, len(handle.tools))
            except (asyncio.TimeoutError, BaseException) as e:
                if isinstance(e, asyncio.TimeoutError):
                    logger.error("MCP server '{}': connection timed out (30s)", name)
                else:
                    logger.error("MCP server '{}': failed to connect: {}", name, e)
                if handle.task and not handle.task.done():
                    handle.task.cancel()
                    try:
                        await handle.task
                    except (asyncio.CancelledError, BaseException):
                        pass

        return all_tools

    async def stop(self) -> None:
        """Signal all server tasks to stop and wait for cleanup."""
        for handle in reversed(self._handles):
            handle.stop_event.set()
            if handle.task:
                try:
                    await asyncio.wait_for(handle.task, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError, BaseException):
                    if handle.task and not handle.task.done():
                        handle.task.cancel()
                        try:
                            await handle.task
                        except (asyncio.CancelledError, BaseException):
                            pass
        self._handles.clear()

    async def _run_server(
        self,
        name: str,
        cfg: Any,
        handle: _ServerHandle,
        ready: asyncio.Future[None],
    ) -> None:
        """Run one MCP connection task and keep it alive until stop is requested."""
        from mcp import ClientSession

        try:
            cm_transport = self._create_transport(cfg)
            async with cm_transport as transport_result:
                if isinstance(transport_result, tuple) and len(transport_result) >= 2:
                    read_stream, write_stream = transport_result[0], transport_result[1]
                else:
                    read_stream, write_stream = transport_result, None

                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    handle.session = session

                    result = await session.list_tools()
                    for tool in result.tools:
                        input_schema = getattr(tool, "inputSchema", None) or {
                            "type": "object",
                            "properties": {},
                        }
                        handle.tools.append(
                            MCPTool(
                                server_name=name,
                                tool_name=tool.name,
                                tool_description=tool.description or tool.name,
                                input_schema=input_schema,
                                session=session,
                            )
                        )

                    if not ready.done():
                        ready.set_result(None)

                    await handle.stop_event.wait()

        except BaseException as e:
            if not ready.done():
                ready.set_exception(e)
            else:
                logger.warning("MCP server '{}': connection lost: {}", name, e)

    @staticmethod
    def _create_transport(cfg: Any) -> Any:
        """Create transport context manager based on MCP server config."""
        transport = cfg.transport

        if transport == "stdio":
            from mcp.client.stdio import StdioServerParameters, stdio_client

            return stdio_client(
                StdioServerParameters(
                    command=cfg.command,
                    args=cfg.args,
                    env=cfg.env if cfg.env else None,
                )
            )

        if transport == "sse":
            from mcp.client.sse import sse_client

            return sse_client(cfg.url)

        if transport == "streamable-http":
            from mcp.client.streamable_http import streamablehttp_client

            return streamablehttp_client(cfg.url)

        raise ValueError(f"Unknown MCP transport: {transport}")
