from dotenv import load_dotenv
from openai import OpenAI
import os
import json
import time
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class BatchRequest:
    custom_id: str
    messages: List[Dict[str, str]]
    metadata: Optional[Dict] = None


@dataclass
class BatchResult:
    custom_id: str
    success: bool
    content: Optional[str] = None
    error_message: Optional[str] = None


class OpenAIQuery:
    """A class for querying OpenAI's GPT models."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, verbose: bool = False):
        """
        Initialize the OpenAI query client.
        If None, loads from environment
        """
        load_dotenv()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.verbose = verbose

        if not api_key:
            raise ValueError(
                "OpenAI API key not found in environment variables or parameters"
            )

        self.client = OpenAI(api_key=api_key)

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
            )

            if stream:
                concat_response = ""
                for chunk in response:
                    content = chunk.choices[0].delta.content
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

    def create_batch_jsonl(self, batch_requests: List[BatchRequest], filename: str) -> str:
        """
        Create a JSONL file for batch processing.

        Args:
            batch_requests: List of batch requests
            filename: Name of the JSONL file to create

        Returns:
            str: Path to the created JSONL file
        """
        if self.verbose:
            print(f"Creating batch JSONL file: {filename}")

        with open(filename, 'w', encoding='utf-8') as f:
            for request in batch_requests:
                batch_item = {
                    "custom_id": request.custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": request.messages,
                        "max_tokens": 1000
                    }
                }
                f.write(json.dumps(batch_item) + '\n')

        if self.verbose:
            print(f"Created JSONL file with {len(batch_requests)} requests")
        
        return filename

    def upload_batch_file(self, jsonl_filename: str) -> str:
        """
        Upload a JSONL file for batch processing.

        Args:
            jsonl_filename: Path to the JSONL file

        Returns:
            str: File ID for the uploaded file
        """
        if self.verbose:
            print(f"Uploading batch file: {jsonl_filename}")

        with open(jsonl_filename, 'rb') as f:
            file_response = self.client.files.create(
                file=f,
                purpose="batch"
            )

        if self.verbose:
            print(f"File uploaded with ID: {file_response.id}")
        
        return file_response.id

    def create_batch(self, file_id: str, description: str = "Fantasy Football Batch") -> str:
        """
        Create a batch processing job.

        Args:
            file_id: ID of the uploaded JSONL file
            description: Optional description for the batch

        Returns:
            str: Batch ID
        """
        if self.verbose:
            print(f"Creating batch with file ID: {file_id}")

        batch_response = self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description}
        )

        if self.verbose:
            print(f"Batch created with ID: {batch_response.id}")
        
        return batch_response.id

    def wait_for_batch_completion(self, batch_id: str, check_interval: int = 30, max_wait_time: int = 3600) -> bool:
        """
        Wait for a batch to complete.

        Args:
            batch_id: ID of the batch to monitor
            check_interval: Seconds between status checks
            max_wait_time: Maximum time to wait in seconds

        Returns:
            bool: True if completed successfully, False if failed or timed out
        """
        if self.verbose:
            print(f"Waiting for batch {batch_id} to complete...")

        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            batch_status = self.client.batches.retrieve(batch_id)
            
            if self.verbose:
                print(f"Batch status: {batch_status.status}")

            if batch_status.status == "completed":
                if self.verbose:
                    print(f"Batch completed successfully!")
                return True
            elif batch_status.status in ["failed", "expired", "cancelled"]:
                if self.verbose:
                    print(f"Batch failed with status: {batch_status.status}")
                return False
            
            time.sleep(check_interval)

        if self.verbose:
            print(f"Batch timed out after {max_wait_time} seconds")
        return False

    def download_batch_results(self, batch_id: str) -> List[BatchResult]:
        """
        Download and parse batch results.

        Args:
            batch_id: ID of the completed batch

        Returns:
            List[BatchResult]: Parsed batch results
        """
        if self.verbose:
            print(f"Downloading results for batch {batch_id}")

        batch_status = self.client.batches.retrieve(batch_id)
        
        if not batch_status.output_file_id:
            raise ValueError("Batch has no output file")

        # Download the output file
        file_response = self.client.files.content(batch_status.output_file_id)
        output_data = file_response.read().decode('utf-8')

        # Parse the results
        results = []
        for line in output_data.strip().split('\n'):
            if not line:
                continue
            
            try:
                result_data = json.loads(line)
                custom_id = result_data.get("custom_id", "")
                
                if result_data.get("error"):
                    results.append(BatchResult(
                        custom_id=custom_id,
                        success=False,
                        error_message=str(result_data["error"])
                    ))
                elif result_data.get("response", {}).get("body", {}).get("choices"):
                    content = result_data["response"]["body"]["choices"][0]["message"]["content"]
                    results.append(BatchResult(
                        custom_id=custom_id,
                        success=True,
                        content=content
                    ))
                else:
                    results.append(BatchResult(
                        custom_id=custom_id,
                        success=False,
                        error_message="No content in response"
                    ))
            except json.JSONDecodeError as e:
                if self.verbose:
                    print(f"Error parsing result line: {e}")
                continue

        if self.verbose:
            print(f"Downloaded {len(results)} results")
        
        return results

    def process_batch(self, batch_requests: List[BatchRequest], batch_name: str = "batch") -> List[BatchResult]:
        """
        Complete batch processing workflow.

        Args:
            batch_requests: List of requests to process
            batch_name: Name for the batch (used for file naming)

        Returns:
            List[BatchResult]: Results from the batch processing
        """
        # Create JSONL file
        jsonl_filename = f"{batch_name}_input.jsonl"
        self.create_batch_jsonl(batch_requests, jsonl_filename)

        try:
            # Upload file
            file_id = self.upload_batch_file(jsonl_filename)
            
            # Create batch
            batch_id = self.create_batch(file_id, f"Fantasy Football Analysis - {batch_name}")
            
            # Wait for completion
            if not self.wait_for_batch_completion(batch_id):
                raise RuntimeError(f"Batch {batch_id} failed to complete")
            
            # Download results
            results = self.download_batch_results(batch_id)
            
            return results

        finally:
            # Clean up local JSONL file
            if os.path.exists(jsonl_filename):
                os.remove(jsonl_filename)

    def cleanup_batch_files(self, batch_name: str):
        """
        Clean up any remaining batch files.

        Args:
            batch_name: Name of the batch to clean up
        """
        files_to_remove = [
            f"{batch_name}_input.jsonl",
            f"{batch_name}_output.jsonl"
        ]
        
        for filename in files_to_remove:
            if os.path.exists(filename):
                os.remove(filename)
                if self.verbose:
                    print(f"Removed file: {filename}")
