from dotenv import load_dotenv
import openai
import os
from typing import Dict, Optional


class OpenAIQuery:
    """A class for querying OpenAI's GPT models."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the OpenAI query client.
        If None, loads from environment
        """
        load_dotenv()
        self.model = model or os.getenv("OPENAI_MODEL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found in environment variables or parameters"
            )

        openai.api_key = self.api_key

    def query(self, messages: list[Dict[str, str]], stream: bool = True) -> str:
        """
        Query OpenAI with a list of messages.

        Args:
            messages (list[Dict[str, str]]): list of message dictionaries
            stream (bool): Whether to stream the response

        Returns:
            str: The complete response from OpenAI
        """
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                stream=stream,
            )

            if stream:
                concat_response = ""
                for chunk in response:
                    content = chunk.choices[0].get("delta", {}).get("content", "")
                    if content:
                        print(content, end="")
                        concat_response += content
                return concat_response
            else:
                return response.choices[0].message.content

        except Exception as e:
            print(f"Error querying OpenAI: {e}")
            raise

    def create_system_user_query(
        self, system_prompt: str, user_prompt: str
    ) -> list[Dict[str, str]]:
        """
        Create a standard system/user message structure.

        Args:
            system_prompt (str): The system prompt
            user_prompt (str): The user prompt

        Returns:
            list[Dict[str, str]]: Formatted messages for OpenAI
        """
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
