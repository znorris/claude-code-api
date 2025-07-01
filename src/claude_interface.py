import asyncio
import json
import logging
from typing import List, Dict, Any, AsyncIterator, Optional
try:
    from .models.openai import ChatMessage
except ImportError:
    from models.openai import ChatMessage

logger = logging.getLogger(__name__)

class ClaudeCodeInterface:
    def __init__(self):
        self.claude_command = "claude"
    
    def _build_command(self, messages: List[ChatMessage], stream: bool = False) -> List[str]:
        cmd = [self.claude_command]
        
        if stream:
            cmd.extend(["--print", "--output-format", "stream-json", "--verbose"])
        else:
            cmd.extend(["--print", "--output-format", "json"])
        
        prompt = self._format_messages_as_prompt(messages)
        cmd.append(prompt)
        
        return cmd
    
    def _format_messages_as_prompt(self, messages: List[ChatMessage]) -> str:
        formatted_messages = []
        
        for message in messages:
            if message.role == "system":
                formatted_messages.append(f"System: {message.content}")
            elif message.role == "user":
                formatted_messages.append(f"User: {message.content}")
            elif message.role == "assistant":
                formatted_messages.append(f"Assistant: {message.content}")
        
        return "\n\n".join(formatted_messages)
    
    async def complete_chat(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        cmd = self._build_command(messages, stream=False)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Claude command failed: {stderr.decode()}")
                raise RuntimeError(f"Claude command failed: {stderr.decode()}")
            
            result = json.loads(stdout.decode())
            
            if result.get("is_error", False):
                raise RuntimeError(f"Claude returned error: {result.get('result', 'Unknown error')}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            raise RuntimeError(f"Failed to parse Claude response: {e}")
        except Exception as e:
            logger.error(f"Claude execution failed: {e}")
            raise RuntimeError(f"Claude execution failed: {e}")
    
    async def stream_chat(self, messages: List[ChatMessage]) -> AsyncIterator[Dict[str, Any]]:
        cmd = self._build_command(messages, stream=True)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                try:
                    chunk = json.loads(line.decode().strip())
                    yield chunk
                except json.JSONDecodeError:
                    continue
            
            await process.wait()
            
            if process.returncode != 0:
                stderr = await process.stderr.read()
                logger.error(f"Claude streaming failed: {stderr.decode()}")
                raise RuntimeError(f"Claude streaming failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Claude streaming execution failed: {e}")
            raise RuntimeError(f"Claude streaming execution failed: {e}")

claude_interface = ClaudeCodeInterface()