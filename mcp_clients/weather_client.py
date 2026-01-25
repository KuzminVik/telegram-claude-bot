#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Weather Client - клиент для работы с погодным сервисом
"""

import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class MCPWeatherClient:
    """Клиент для взаимодействия с MCP Weather Server"""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        self.lock = asyncio.Lock()
        
    async def start(self):
        """Запустить MCP сервер"""
        try:
            self.process = await asyncio.create_subprocess_exec(
                'node', self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Читаем первую строку из stderr (приветствие сервера)
            if self.process.stderr:
                greeting = await self.process.stderr.readline()
                logger.info(f"MCP Server: {greeting.decode().strip()}")
            
            logger.info("✓ MCP Weather Server started")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP Weather Server: {e}")
            return False
    
    async def stop(self):
        """Остановить MCP сервер"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            logger.info("✓ MCP Weather Server stopped")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Вызвать инструмент MCP сервера"""
        if not self.process:
            logger.error("MCP Weather Server is not running")
            return None
        
        async with self.lock:
            try:
                request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": 1
                }
                
                request_json = json.dumps(request) + '\n'
                logger.info(f"Sending to MCP: {request_json.strip()}")
                
                self.process.stdin.write(request_json.encode())
                await self.process.stdin.drain()
                
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=10.0
                )
                
                response_text = response_line.decode().strip()
                logger.info(f"Received from MCP: {response_text[:200]}...")
                
                response = json.loads(response_text)
                
                if 'result' in response:
                    content = response['result']['content'][0]['text']
                    return json.loads(content)
                elif 'error' in response:
                    logger.error(f"MCP tool call error: {response['error']}")
                    return None
                else:
                    logger.error(f"Unexpected MCP response format: {response}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.error("MCP tool call timeout")
                return None
            except Exception as e:
                logger.error(f"Error calling MCP tool: {e}")
                return None
