#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Ollama Client - клиент для работы с RAG через Ollama
"""

import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class MCPOllamaClient:
    """Клиент для взаимодействия с MCP Ollama Server (RAG)"""
    
    def __init__(self, ssh_host: str, ssh_port: int, ssh_user: str, ssh_key: str, 
                 node_path: str, server_path: str):
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_user = ssh_user
        self.ssh_key = ssh_key
        self.node_path = node_path
        self.server_path = server_path
        self.process = None
        self.lock = asyncio.Lock()
        
    async def start(self):
        """Запустить MCP сервер через SSH"""
        try:
            ssh_command = [
                'ssh',
                '-i', self.ssh_key,
                '-p', str(self.ssh_port),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{self.ssh_user}@{self.ssh_host}',
                f'{self.node_path} {self.server_path}'
            ]
            
            self.process = await asyncio.create_subprocess_exec(
                *ssh_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                greeting = await asyncio.wait_for(
                    self.process.stderr.readline(),
                    timeout=5.0
                )
                logger.info(f"MCP Ollama Server: {greeting.decode().strip()}")
            except asyncio.TimeoutError:
                logger.warning("No greeting from MCP Ollama Server")
            
            logger.info("✓ MCP Ollama Server started (via SSH)")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP Ollama Server: {e}")
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
            logger.info("✓ MCP Ollama Server stopped")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Вызвать инструмент MCP сервера"""
        if not self.process:
            logger.error("MCP Ollama Server is not running")
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
                logger.info(f"Sending to MCP Ollama: {request_json.strip()}")
                
                self.process.stdin.write(request_json.encode())
                await self.process.stdin.drain()
                
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=60.0  # RAG может занять больше времени
                )
                
                response_text = response_line.decode().strip()
                logger.info(f"Received from MCP Ollama: {response_text[:200]}...")
                
                response = json.loads(response_text)
                
                if 'result' in response:
                    content = response['result']['content'][0]['text']
                    return json.loads(content)
                elif 'error' in response:
                    logger.error(f"MCP Ollama error: {response['error']}")
                    return None
                else:
                    logger.error(f"Unexpected response: {response}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.error("MCP Ollama timeout")
                return None
            except Exception as e:
                logger.error(f"Error calling MCP Ollama: {e}")
                return None
