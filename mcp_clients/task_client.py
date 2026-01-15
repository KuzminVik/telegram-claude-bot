import asyncio
import json
import logging
import subprocess
from config import MCP_TASK_NODE_PATH, MCP_TASK_SERVER_PATH

logger = logging.getLogger(__name__)

class TaskMCPClient:
    def __init__(self):
        self.process = None
        self.reader = None
        self.writer = None
        self.request_id = 0

    async def start(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                MCP_TASK_NODE_PATH,
                MCP_TASK_SERVER_PATH,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.reader = self.process.stdout
            self.writer = self.process.stdin
            
            stderr_line = await asyncio.wait_for(self.process.stderr.readline(), timeout=5)
            logger.info(f"MCP Task Server: {stderr_line.decode().strip()}")
            logger.info("✓ MCP Task Server started")
            return True
        except Exception as e:
            logger.error(f"Failed to start Task MCP Server: {e}")
            return False

    async def stop(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()

    async def call_tool(self, tool_name, arguments=None):
        if not self.writer or not self.reader:
            raise RuntimeError("Task MCP client not started")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            },
            "id": self.request_id
        }
        
        request_json = json.dumps(request) + "\n"
        self.writer.write(request_json.encode())
        await self.writer.drain()
        
        response_line = await self.reader.readline()
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        result = response.get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result

    async def get_tasks(self, status=None, priority=None, assignee=None, tag=None):
        args = {}
        if status:
            args["status"] = status
        if priority:
            args["priority"] = priority
        if assignee:
            args["assignee"] = assignee
        if tag:
            args["tag"] = tag
        return await self.call_tool("get_tasks", args)

    async def create_task(self, title, priority, description=None, assignee=None, 
                         due_date=None, tags=None, estimated_hours=None):
        args = {
            "title": title,
            "priority": priority
        }
        if description:
            args["description"] = description
        if assignee:
            args["assignee"] = assignee
        if due_date:
            args["due_date"] = due_date
        if tags:
            args["tags"] = tags
        if estimated_hours:
            args["estimated_hours"] = estimated_hours
        return await self.call_tool("create_task", args)

    async def update_task(self, task_id, **kwargs):
        args = {"task_id": task_id}
        args.update(kwargs)
        return await self.call_tool("update_task", args)

    async def get_stats(self):
        return await self.call_tool("get_task_stats")
