import asyncio
import json
import logging
import base64
import httpx
from typing import List, Dict, Any, AsyncIterator, Optional, Union
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
    
    async def _download_image_as_base64(self, url: str) -> tuple[str, str]:
        """Download image from URL and return base64 data and media type."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Determine media type from content-type header or URL extension
                content_type = response.headers.get('content-type', '')
                if content_type.startswith('image/'):
                    media_type = content_type
                else:
                    # Fallback to URL extension
                    if url.lower().endswith('.png'):
                        media_type = 'image/png'
                    elif url.lower().endswith('.jpg') or url.lower().endswith('.jpeg'):
                        media_type = 'image/jpeg'
                    elif url.lower().endswith('.gif'):
                        media_type = 'image/gif'
                    elif url.lower().endswith('.webp'):
                        media_type = 'image/webp'
                    else:
                        media_type = 'image/jpeg'  # Default
                
                # Convert to base64
                base64_data = base64.b64encode(response.content).decode('utf-8')
                return base64_data, media_type
                
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise RuntimeError(f"Failed to download image: {e}")
    
    def _extract_base64_from_data_url(self, data_url: str) -> tuple[str, str]:
        """Extract base64 data and media type from data URL."""
        if not data_url.startswith('data:'):
            raise ValueError("Invalid data URL format")
        
        try:
            # Parse data:image/jpeg;base64,<data>
            header, data = data_url.split(',', 1)
            media_type_part = header.split(';')[0].replace('data:', '')
            
            # Validate media type
            if not media_type_part.startswith('image/'):
                raise ValueError(f"Unsupported media type: {media_type_part}")
                
            return data, media_type_part
            
        except Exception as e:
            logger.error(f"Failed to parse data URL: {e}")
            raise ValueError(f"Invalid data URL format: {e}")
    
    async def _convert_content_to_claude_format(self, content: Union[str, List]) -> List[Dict[str, Any]]:
        """Convert OpenAI content format to Claude content blocks."""
        if isinstance(content, str):
            # Simple text content
            return [{
                "type": "text",
                "text": content
            }]
        
        # Array of content items
        claude_content = []
        
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    claude_content.append({
                        "type": "text",
                        "text": item.get("text", "")
                    })
                elif item.get("type") == "image_url":
                    image_url_data = item.get("image_url", {})
                    url = image_url_data.get("url", "")
                    
                    if url.startswith('data:'):
                        # Base64 data URL
                        base64_data, media_type = self._extract_base64_from_data_url(url)
                    else:
                        # HTTP/HTTPS URL - download and convert
                        base64_data, media_type = await self._download_image_as_base64(url)
                    
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    })
            else:
                # Handle ContentText/ContentImageUrl objects
                if hasattr(item, 'type'):
                    if item.type == "text":
                        claude_content.append({
                            "type": "text",
                            "text": item.text
                        })
                    elif item.type == "image_url":
                        image_url_data = item.image_url
                        url = image_url_data.get("url", "")
                        
                        if url.startswith('data:'):
                            base64_data, media_type = self._extract_base64_from_data_url(url)
                        else:
                            base64_data, media_type = await self._download_image_as_base64(url)
                        
                        claude_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data
                            }
                        })
        
        return claude_content
    
    async def _format_messages_as_json(self, messages: List[ChatMessage]) -> str:
        """Format messages as JSON stream for Claude Code CLI."""
        # Extract system messages and latest user message
        system_messages = [msg for msg in messages if msg.role == "system"]
        latest_user_message = None
        
        for message in reversed(messages):
            if message.role == "user":
                latest_user_message = message
                break
        
        if not latest_user_message:
            return ""
        
        # Convert user message content to Claude format (handles images)
        claude_content = await self._convert_content_to_claude_format(latest_user_message.content)
        
        # Build user message with optional system prompt
        user_obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": claude_content
            }
        }
        
        # Add system message if present (use the last system message)
        if system_messages:
            # System message content should be text only
            system_content = system_messages[-1].content
            if isinstance(system_content, list):
                # Extract text from content array if needed
                system_text = ""
                for item in system_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        system_text += item.get("text", "")
                    elif hasattr(item, 'type') and item.type == "text":
                        system_text += item.text
                user_obj["system"] = system_text
            else:
                user_obj["system"] = system_content
            
        return json.dumps(user_obj)
    
    async def complete_chat(self, messages: List[ChatMessage], model: str = "sonnet", use_json_input: bool = True, claude_session_id: Optional[str] = None) -> Dict[str, Any]:
        cmd = self._build_command(messages, model, stream=False, use_json_input=use_json_input, claude_session_id=claude_session_id)
        
        try:
            if use_json_input:
                json_input = await self._format_messages_as_json(messages)
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
                json_input = await self._format_messages_as_json(messages)
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