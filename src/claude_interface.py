import asyncio
import json
import logging
from typing import List, Dict, Any, AsyncIterator, Optional
try:
    from .models.openai import ChatMessage
    from .models.config import validate_model
except ImportError:
    from models.openai import ChatMessage
    from models.config import validate_model

logger = logging.getLogger(__name__)

class ClaudeCodeInterface:
    def __init__(self):
        self.claude_command = "claude"
    
    def _build_command(self, messages: List[ChatMessage], model: str, stream: bool = False, use_json_input: bool = True, claude_session_id: Optional[str] = None) -> List[str]:
        cmd = [self.claude_command]
        
        # Validate and pass through model name directly to Claude Code
        validated_model = validate_model(model)
        cmd.extend(["--model", validated_model])
        
        # Resume existing session if provided
        if claude_session_id:
            cmd.extend(["--resume", claude_session_id])
        
        if use_json_input:
            cmd.extend(["--input-format", "stream-json"])
            cmd.extend(["--print", "--output-format", "stream-json", "--verbose"])
        else:
            if stream:
                cmd.extend(["--print", "--output-format", "stream-json", "--verbose"])
            else:
                cmd.extend(["--print", "--output-format", "json"])
        
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
    
    def _format_messages_as_json(self, messages: List[ChatMessage]) -> str:
        """Format messages as JSON stream for Claude Code CLI."""
        # With session management, we only send the latest user message
        # Claude CLI will maintain conversation context via --resume
        latest_user_message = None
        for message in reversed(messages):
            if message.role == "user":
                latest_user_message = message
                break
        
        if not latest_user_message:
            return ""
            
        json_obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": latest_user_message.content
                }]
            }
        }
        return json.dumps(json_obj)
    
    async def complete_chat(self, messages: List[ChatMessage], model: str = "sonnet", use_json_input: bool = True, claude_session_id: Optional[str] = None) -> Dict[str, Any]:
        cmd = self._build_command(messages, model, stream=False, use_json_input=use_json_input, claude_session_id=claude_session_id)
        
        try:
            if use_json_input:
                json_input = self._format_messages_as_json(messages)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate(input=json_input.encode())
            else:
                prompt = self._format_messages_as_prompt(messages)
                cmd.append(prompt)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Claude command failed: {stderr.decode()}")
                raise RuntimeError(f"Claude command failed: {stderr.decode()}")
            
            if use_json_input:
                # Parse stream-json output for multiple lines
                lines = stdout.decode().strip().split('\n')
                result_data = None
                claude_session_id = None
                
                for line in lines:
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            if chunk.get("type") == "result":
                                result_data = chunk
                                claude_session_id = chunk.get("session_id")
                            elif chunk.get("type") == "system" and chunk.get("subtype") == "init":
                                if not claude_session_id:  # Use init session_id as fallback
                                    claude_session_id = chunk.get("session_id")
                        except json.JSONDecodeError:
                            continue
                
                if not result_data:
                    raise RuntimeError("No result found in Claude output")
                    
                if result_data.get("is_error", False):
                    raise RuntimeError(f"Claude returned error: {result_data.get('result', 'Unknown error')}")
                
                # Add Claude session ID to result for caller to use
                result_data["claude_session_id"] = claude_session_id
                return result_data
            else:
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
    
    async def stream_chat(self, messages: List[ChatMessage], model: str = "sonnet", use_json_input: bool = True, claude_session_id: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        cmd = self._build_command(messages, model, stream=True, use_json_input=use_json_input, claude_session_id=claude_session_id)
        
        try:
            if use_json_input:
                json_input = self._format_messages_as_json(messages)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                # Send JSON input and close stdin
                process.stdin.write(json_input.encode())
                process.stdin.close()
            else:
                prompt = self._format_messages_as_prompt(messages)
                cmd.append(prompt)
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