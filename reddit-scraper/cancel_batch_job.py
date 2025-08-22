#!/usr/bin/env python3
"""
Cancel a running batch job.
Reads the saved batch ID and cancels the batch processing.
"""

from OpenAIQuery import OpenAIQuery
import json
import os
from datetime import datetime

# Configuration
OPENAI_MODEL = "gpt-5-mini"  # Should match submit script
BATCH_ID_FILE = "batch_info.json"


def update_batch_info(status: str, cancellation_time: str = None):
    """Update the batch info file with cancellation status."""
    if not os.path.exists(BATCH_ID_FILE):
        return
    
    with open(BATCH_ID_FILE, "r") as f:
        batch_info = json.load(f)
    
    batch_info["status"] = status
    if cancellation_time:
        batch_info["cancelled_at"] = cancellation_time
    
    with open(BATCH_ID_FILE, "w") as f:
        json.dump(batch_info, f, indent=2)


def main():
    # Check for saved batch info
    if not os.path.exists(BATCH_ID_FILE):
        print(f"❌ No batch info found!")
        print(f"   Expected file: {BATCH_ID_FILE}")
        print(f"   No batch to cancel.")
        return

    # Load batch info
    with open(BATCH_ID_FILE, "r") as f:
        batch_info = json.load(f)

    batch_id = batch_info["batch_id"]
    batch_name = batch_info.get("batch_name", "unknown")
    player_count = batch_info.get("player_count", "unknown")
    submitted_at = batch_info.get("submitted_at", "unknown")
    current_status = batch_info.get("status", "unknown")

    print(f"🚫 Cancelling batch job...")
    print(f"   Batch ID: {batch_id}")
    print(f"   Batch Name: {batch_name}")
    print(f"   Submitted: {submitted_at}")
    print(f"   Current Status: {current_status}")
    print(f"   Player Count: {player_count}")

    # Initialize OpenAI client
    openai_client = OpenAIQuery(model=OPENAI_MODEL, verbose=True)

    try:
        # Check current batch status before cancelling
        print(f"\n🔍 Checking current batch status...")
        batch = openai_client.client.batches.retrieve(batch_id)
        
        print(f"   Current Status: {batch.status}")
        if hasattr(batch, 'request_counts') and batch.request_counts:
            print(f"   Request Counts: {batch.request_counts}")
        
        # Check if batch can be cancelled
        if batch.status in ["cancelled", "completed", "failed", "expired"]:
            print(f"⚠️  Batch cannot be cancelled - it's already {batch.status}")
            update_batch_info(batch.status)
            return
        
        if batch.status in ["cancelling"]:
            print(f"⏳ Batch is already being cancelled...")
            update_batch_info("cancelling")
            return

        # Cancel the batch
        print(f"\n🚫 Cancelling batch {batch_id}...")
        cancelled_batch = openai_client.client.batches.cancel(batch_id)
        
        print(f"✅ Batch cancellation requested!")
        print(f"   New Status: {cancelled_batch.status}")
        
        # Update batch info
        update_batch_info(cancelled_batch.status, datetime.now().isoformat())
        
        if cancelled_batch.status == "cancelling":
            print(f"⏳ Batch is being cancelled... This may take a few moments.")
            print(f"   You can check the status later with: python get_batch_results.py")
        elif cancelled_batch.status == "cancelled":
            print(f"✅ Batch successfully cancelled!")
        
        # Show what was saved
        if hasattr(cancelled_batch, 'request_counts') and cancelled_batch.request_counts:
            total_requests = cancelled_batch.request_counts.get('total', 0)
            completed_requests = cancelled_batch.request_counts.get('completed', 0)
            print(f"\n📊 Cancellation Summary:")
            print(f"   Total Requests: {total_requests}")
            print(f"   Completed Before Cancellation: {completed_requests}")
            if completed_requests > 0:
                print(f"   💡 Note: {completed_requests} requests may have completed before cancellation")
                print(f"      You can still run 'python get_batch_results.py' to retrieve any completed results")

    except Exception as e:
        print(f"❌ Error cancelling batch: {e}")
        return


if __name__ == "__main__":
    main()

