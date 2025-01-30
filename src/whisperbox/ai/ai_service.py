from typing import Optional, Type, TypeVar, Union, Any
from anthropic import Anthropic
from anthropic.types import ContentBlock, Message
from groq import Groq
import ollama
from openai import OpenAI
from pydantic import BaseModel
import json
from ..core.config import config
import os

T = TypeVar('T', bound=BaseModel)

class AIService:
    # These are only used as fallbacks if config.yaml doesn't specify a model
    DEFAULT_MODELS = {
        "ollama": "llama3.2",
        "groq": "mixtral-8x7b-32768",
        "anthropic": "claude-3-sonnet",
        "openai": "gpt-4",
    }

    def __init__(self, service_type: Optional[str] = None, model: Optional[str] = None):
        """Initialize the AI service.
        
        Args:
            service_type: The type of AI service to use (groq, anthropic, openai, ollama)
            model: The specific model to use. If not provided, uses config.yaml or default model.
        """
        self.service_type = service_type.lower() if service_type else config.ai.get('default_provider', "ollama")
        
        # First try model param, then config.yaml, then fallback to defaults
        self.model = (
            model or 
            config.ai.get('default_model') or 
            self.DEFAULT_MODELS[self.service_type]
        )
        
        if self.service_type == "groq":
            self.client = Groq(api_key=self._get_api_key("groq"))
        elif self.service_type == "anthropic":
            self.client = Anthropic(api_key=self._get_api_key("anthropic"))
        elif self.service_type == "openai":
            self.client = OpenAI(api_key=self._get_api_key("openai"))
        elif self.service_type == "ollama":
            self.client = ollama
        else:
            raise ValueError(
                f"Invalid AI provider: {service_type}. "
                "Must be one of: ollama, groq, anthropic, openai"
            )

    def _get_api_key(self, provider: str) -> str:
        """Get API key from config or environment variables.
        
        Args:
            provider: The AI provider name (groq, anthropic, openai)
            
        Returns:
            str: The API key if found
            
        Raises:
            ValueError: If no API key is found
        """
        # Try config first
        config_key = config.get_api_key(provider)
        if config_key:
            return config_key
        
        # Try environment variables
        env_var_map = {
            "groq": "GROQ_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY"
        }
        
        env_var = env_var_map.get(provider)
        if env_var:
            env_key = os.getenv(env_var)
            if env_key:
                return env_key
            
        raise ValueError(
            f"No API key found for {provider}. Please set it in the config file "
            f"or set the {env_var} environment variable."
        )

    def query(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Query AI with optional system prompt"""
        for _ in range(3):  # max_retries
            try:
                if self.service_type == "ollama":
                    return self._query_ollama(prompt, system_prompt)
                elif self.service_type == "groq":
                    return self._query_groq(prompt, system_prompt, max_tokens)
                elif self.service_type == "anthropic":
                    response = self._query_anthropic(prompt, system_prompt, max_tokens)
                    return response
                elif self.service_type == "openai":
                    return self._query_openai(prompt, system_prompt, max_tokens)
                else:
                    raise ValueError(f"Unsupported service type: {self.service_type}")
            except Exception as e:
                print(f"Error occurred: {e}. Retrying...")
        raise Exception(f"Failed to query {self.service_type} after 3 attempts")

    def _query_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    def _query_groq(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content

    def _query_anthropic(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Query Anthropic's Claude API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response: Message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    def _query_openai(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024) -> str:
        """Query OpenAI's API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content

    def openai_structured_output(self, system_prompt: str, user_prompt: str, data_model: Type[T]) -> T:
        """Query OpenAI with structured output using Pydantic model"""
        if self.service_type != "openai":
            raise ValueError("Structured output is only available with OpenAI service")
            
        try:
            completion = self.client.chat.completions.create(
                model=self.model,  # Use configured model instead of hardcoded one
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            response_text = completion.choices[0].message.content
            if response_text:
                return data_model.parse_raw(response_text)
            raise ValueError("Empty response from OpenAI")
        except Exception as e:
            print(f"Error in OpenAI structured output: {e}")
            raise

    def query_structured(self, prompt: str, data_model: Type[T], system_prompt: str = "") -> T:
        """Query with structured output (OpenAI only)"""
        if self.service_type != "openai":
            raise ValueError(
                "Structured output requires OpenAI service. "
                "Initialize AIService with service_type='openai' to use this feature."
            )
            
        return self.openai_structured_output(system_prompt, prompt, data_model)
