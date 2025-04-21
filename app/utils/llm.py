import os
import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Dict, Any, Optional, Union

from pydantic import BaseModel, ValidationError
from openai import OpenAI, AsyncOpenAI

# Define a generic type variable for Pydantic models
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)

# --- 1. Define the Abstract Base Class (Interface) ---

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients supporting structured output."""

    @abstractmethod
    def generate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> PydanticModel:
        pass

    @abstractmethod
    async def agenerate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> PydanticModel:
        pass

    @abstractmethod
    def embed_texts(
        self,
        texts: List[str],
        model_name: str,
        **kwargs: Any
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        Returns a list of embedding vectors (one per input text).
        """
        pass

# --- 2. Implement the OpenAI Client ---

class OpenAIClient(BaseLLMClient):
    """LLM Client implementation for OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, client: Optional[OpenAI] = None, aclient: Optional[AsyncOpenAI] = None):
        if client:
            self.client = client
        else:
            self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        if aclient:
            self.aclient = aclient
        else:
            self.aclient = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        if not self.client.api_key:
            raise ValueError("OpenAI API key is required. Provide it via api_key argument or OPENAI_API_KEY environment variable.")

    def generate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> PydanticModel:
        try:
            completion = self.client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=pydantic_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            result_object = completion.choices[0].message.parsed
            if not isinstance(result_object, pydantic_model):
                raise TypeError(f"Parsed object is not of type {pydantic_model.__name__}, got {type(result_object)}")
            return result_object
        except Exception as e:
            raise

    async def agenerate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> PydanticModel:
        try:
            completion = await self.aclient.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=pydantic_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            result_object = completion.choices[0].message.parsed
            if not isinstance(result_object, pydantic_model):
                raise TypeError(f"Parsed object is not of type {pydantic_model.__name__}, got {type(result_object)}")
            return result_object
        except Exception as e:
            raise

    def embed_texts(
        self,
        texts: List[str],
        model_name: str,
        **kwargs: Any
    ) -> List[List[float]]:
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=model_name,
                **kwargs
            )
            # OpenAI returns a list of objects with .embedding
            return [item.embedding for item in response.data]
        except Exception as e:
            raise

# --- 3. Implement the vLLM Client (via OpenAI Compatible Endpoint) ---

class VLLMClient(BaseLLMClient):
    """
    LLM Client implementation for a vLLM server running an
    OpenAI-compatible endpoint.
    """

    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "dummy-key", client: Optional[OpenAI] = None, aclient: Optional[AsyncOpenAI] = None):
        if client:
            self.client = client
        else:
            self.client = OpenAI(base_url=base_url, api_key=api_key)

        if aclient:
            self.aclient = aclient
        else:
            self.aclient = AsyncOpenAI(base_url=base_url, api_key=api_key)

        self.base_url = base_url

    def generate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        **kwargs: Any
    ) -> PydanticModel:
        try:
            json_schema = pydantic_model.model_json_schema()
            extra_body = {"guided_json": json_schema}
            if kwargs:
                extra_body.update(kwargs)
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                extra_body=extra_body
            )
            raw_response_content = completion.choices[0].message.content
            if not raw_response_content:
                raise ValueError("vLLM returned empty content.")
            validated_data = pydantic_model.model_validate_json(raw_response_content)
            return validated_data
        except (json.JSONDecodeError, ValidationError) as e:
            raise Exception(f"Failed to get valid structured output from vLLM: {e}") from e
        except Exception as e:
            raise

    async def agenerate_structured_output(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        pydantic_model: Type[PydanticModel],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        **kwargs: Any
    ) -> PydanticModel:
        raw_response_content = None
        try:
            json_schema = pydantic_model.model_json_schema()
            extra_body = {"guided_json": json_schema}
            if kwargs:
                extra_body.update(kwargs)
            completion = await self.aclient.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                extra_body=extra_body
            )
            raw_response_content = completion.choices[0].message.content
            if not raw_response_content:
                raise ValueError("vLLM returned empty content.")
            validated_data = pydantic_model.model_validate_json(raw_response_content)
            return validated_data
        except (json.JSONDecodeError, ValidationError) as e:
            raise Exception(f"Failed to get valid structured output from async vLLM: {e}") from e
        except Exception as e:
            raise

    def embed_texts(
        self,
        texts: List[str],
        model_name: str,
        **kwargs: Any
    ) -> List[List[float]]:
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=model_name,
                **kwargs
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise

# --- 4. Factory Method ---

def get_llm_client() -> BaseLLMClient:
    """
    Factory method to get the correct LLM client based on USE_OPENAI env var.
    If USE_OPENAI is set to "1", "true", or "yes" (case-insensitive), use OpenAI.
    Otherwise, use vLLM.
    """
    use_openai = os.getenv("USE_OPENAI", "1").lower() in ("1", "true", "yes")
    if use_openai:
        return OpenAIClient()
    else:
        vllm_base = os.getenv("VLLM_BASE", "http://localhost:8000/v1")
        return VLLMClient(base_url=vllm_base)
