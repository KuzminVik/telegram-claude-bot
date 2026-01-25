#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP GitHub Client - клиент для работы с GitHub репозиториями
"""

import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class MCPGitHubClient:
    """Клиент для взаимодействия с MCP GitHub Server"""
    
    def __init__(self, server_path: str, github_token: str):
        self.server_path = server_path
        self.github_token = github_token
        self.process = None
        self.lock = asyncio.Lock()
        
    async def start(self):
        """Запустить MCP GitHub сервер"""
        try:
            # Запускаем сервер с переменной окружения GITHUB_TOKEN
            env = {
                'GITHUB_TOKEN': self.github_token,
                'PATH': '/usr/bin:/bin:/usr/local/bin:/usr/local/sbin',
                'NODE_PATH': '/usr/local/lib/node_modules'
            }
            
            self.process = await asyncio.create_subprocess_exec(
                'node', self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Читаем приветствие сервера
            if self.process.stderr:
                try:
                    greeting = await asyncio.wait_for(
                        self.process.stderr.readline(),
                        timeout=5.0
                    )
                    logger.info(f"MCP GitHub Server: {greeting.decode().strip()}")
                except asyncio.TimeoutError:
                    logger.warning("No greeting from MCP GitHub Server")
            
            logger.info("✓ MCP GitHub Server started")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP GitHub Server: {e}")
            return False
    
    async def stop(self):
        """Остановить MCP GitHub сервер"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            logger.info("✓ MCP GitHub Server stopped")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Вызвать инструмент MCP GitHub сервера"""
        if not self.process:
            logger.error("MCP GitHub Server is not running")
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
                logger.info(f"Sending to MCP GitHub: {tool_name}")
                
                self.process.stdin.write(request_json.encode())
                await self.process.stdin.drain()
                
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=30.0
                )
                
                response_text = response_line.decode().strip()
                logger.info(f"Received from MCP GitHub: {response_text[:200]}...")
                
                response = json.loads(response_text)
                
                if 'result' in response:
                    content = response['result']['content'][0]['text']
                    return json.loads(content)
                elif 'error' in response:
                    logger.error(f"MCP GitHub error: {response['error']}")
                    return None
                else:
                    logger.error(f"Unexpected response: {response}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.error("MCP GitHub timeout")
                return None
            except Exception as e:
                logger.error(f"Error calling MCP GitHub: {e}")
                return None
    
    async def search_code(self, owner: str, repo: str, query: str, path: str = None) -> dict:
        """Поиск по коду в репозитории"""
        # Формируем GitHub search query
        search_query = f"{query} repo:{owner}/{repo}"
    
        arguments = {
            "q": search_query
        }
        
        if path:
            arguments["path"] = path
        
        return await self.call_tool("search_code", arguments)
    
    async def get_file_contents(self, owner: str, repo: str, path: str, ref: str = None) -> dict:
        """Получить содержимое файла"""
        arguments = {
            "owner": owner,
            "repo": repo,
            "path": path
        }
        
        if ref:
            arguments["ref"] = ref
        
        return await self.call_tool("get_file_contents", arguments)
