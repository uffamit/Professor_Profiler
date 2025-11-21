"""Agent implementation with Gemini API integration."""
import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from google.genai import types as genai_types


class Agent:
    """Agent powered by LLM with support for tools and sub-agents."""
    
    def __init__(
        self,
        name: str,
        model: str,
        description: str = "",
        instruction: str = "",
        tools: Optional[List[Any]] = None,
        sub_agents: Optional[List['Agent']] = None,
        output_key: Optional[str] = None,
        after_agent_callback: Optional[Callable] = None,
        **kwargs
    ):
        self.name = name
        self.model = model
        self.description = description
        self.instruction = instruction
        self.tools = tools or []
        self.sub_agents = sub_agents or []
        self.output_key = output_key
        self.after_agent_callback = after_agent_callback
        self.kwargs = kwargs
        
        # State
        self.client = None
        self.context = {}
        
    def __repr__(self):
        return f"Agent(name='{self.name}', model='{self.model}')"
    
    async def initialize(self, client):
        """Initialize agent with Gemini client."""
        self.client = client
        for sub_agent in self.sub_agents:
            await sub_agent.initialize(client)
        
    async def run(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute agent with given prompt and context."""
        if not self.client:
            raise RuntimeError(f"Agent {self.name} not initialized with client")
        
        self.context = context or {}
        
        # Build system instruction
        system_instruction = self._build_system_instruction()
        
        # Build prompt with context
        full_prompt = self._build_full_prompt(prompt)
        
        # Prepare tool declarations for Gemini
        tool_config = self._prepare_tool_config()
        
        # Execute LLM call
        try:
            response = await self._execute_llm(full_prompt, system_instruction, tool_config)
            
            # Execute sub-agents if any
            if self.sub_agents:
                response = await self._execute_sub_agents(response)
            
            # Apply callback if defined
            if self.after_agent_callback:
                from .callback_context import CallbackContext
                ctx = CallbackContext(agent=self, response=response)
                callback_result = self.after_agent_callback(ctx)
                if callback_result:
                    response = callback_result
            
            return {
                "agent": self.name,
                "response": response,
                "output_key": self.output_key
            }
            
        except Exception as e:
            return {
                "agent": self.name,
                "error": str(e),
                "output_key": self.output_key
            }
    
    def _build_system_instruction(self) -> str:
        """Build system instruction including agent role."""
        parts = []
        
        if self.description:
            parts.append(f"Role: {self.description}")
        
        if self.instruction:
            parts.append(f"Instructions: {self.instruction}")
        
        if self.tools:
            tool_names = [getattr(t, 'name', 'tool') for t in self.tools]
            parts.append(f"Available tools: {', '.join(tool_names)}")
        
        if self.sub_agents:
            agent_names = [a.name for a in self.sub_agents]
            parts.append(f"Sub-agents: {', '.join(agent_names)}")
        
        return "\n\n".join(parts)
    
    def _build_full_prompt(self, prompt: str) -> str:
        """Build prompt with context."""
        if not self.context:
            return prompt
        
        context_str = "\n\nContext:\n"
        for key, value in self.context.items():
            if isinstance(value, dict) or isinstance(value, list):
                context_str += f"- {key}: {json.dumps(value, indent=2)}\n"
            else:
                context_str += f"- {key}: {value}\n"
        
        return prompt + context_str
    
    def _prepare_tool_config(self) -> Optional[Dict[str, Any]]:
        """Prepare tool configuration for Gemini."""
        if not self.tools:
            return None
        
        # Convert tools to Gemini function declarations
        tool_declarations = []
        for tool in self.tools:
            if hasattr(tool, 'to_gemini_declaration'):
                tool_declarations.append(tool.to_gemini_declaration())
        
        if not tool_declarations:
            return None
        
        return {
            "function_declarations": tool_declarations
        }
    
    async def _execute_llm(
        self,
        prompt: str,
        system_instruction: str,
        tool_config: Optional[Dict[str, Any]]
    ) -> str:
        """Execute LLM with prompt and tools."""
        from google import genai
        
        # Build generation config
        config = {
            "temperature": self.kwargs.get("temperature", 0.7),
            "top_p": self.kwargs.get("top_p", 0.95),
            "top_k": self.kwargs.get("top_k", 40),
            "max_output_tokens": self.kwargs.get("max_output_tokens", 2048),
        }
        
        # Create contents
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=prompt)]
            )
        ]
        
        # Add system instruction and tools if available
        generate_kwargs = {
            "model": self.model,
            "contents": contents,
            "config": genai_types.GenerateContentConfig(**config)
        }
        
        if system_instruction:
            generate_kwargs["config"].system_instruction = system_instruction
        
        if tool_config:
            generate_kwargs["config"].tools = [tool_config]
        
        # Generate response
        response = await self.client.aio.models.generate_content(**generate_kwargs)
        
        # Handle tool calls if present
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content.parts:
                # Check for function calls
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute tool and continue
                        tool_result = await self._execute_tool_call(part.function_call)
                        # In production, you'd send tool result back to model
                        return tool_result
                
                # Return text response
                return candidate.content.parts[0].text
        
        return str(response.text) if hasattr(response, 'text') else ""
    
    async def _execute_tool_call(self, function_call) -> str:
        """Execute a tool/function call."""
        function_name = function_call.name
        args = dict(function_call.args) if hasattr(function_call, 'args') else {}
        
        # Find matching tool
        for tool in self.tools:
            if hasattr(tool, 'name') and tool.name == function_name:
                if hasattr(tool, 'execute'):
                    result = await tool.execute(**args)
                    return json.dumps(result)
                elif hasattr(tool, 'func'):
                    result = tool.func(**args)
                    return json.dumps(result)
        
        return json.dumps({"error": f"Tool {function_name} not found"})
    
    async def _execute_sub_agents(self, parent_response: str) -> str:
        """Execute sub-agents in sequence."""
        results = [f"[{self.name} Initial Response]\n{parent_response}"]
        
        for sub_agent in self.sub_agents:
            result = await sub_agent.run(
                prompt=parent_response,
                context=self.context
            )
            response_text = result.get("response", "")
            results.append(f"\n[{sub_agent.name} Response]\n{response_text}")
        
        return "\n".join(results)
