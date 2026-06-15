"""
generate_synthetic_data.py

Creates synthetic request and response data for the request-response-tracker.
The data is intentionally messy so the matching logic has real work to do:
  - request IDs are buried inside free text message fields
  - responses occur at all hours, including nights and weekends
  - some duplicate and system generated rows are added as noise

All data is randomly generated. It contains no real or proprietary information.

Usage:
    python generate_synthetic_data.py
This writes requests.csv and responses.csv to the current folder.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)  # Reproducible: same data every run.

NUM_REQUESTS = 300
START_DATE = datetime.now() - timedelta(days=120)

REQUESTERS = ["field_tech", "site_lead", "dispatcher", "vendor_portal"]
RESPONDERS = ["approver_a", "approver_b", "approver_c"]


def random_datetime(base, max_days=10):
    """A random datetime within max_days after base, at any hour."""
    offset_minutes = random.randint(30, max_days * 24 * 60)
    return base + timedelta(minutes=offset_minutes)


def build_data(num_requests):
    requests = []
    responses = []

    for i in range(1, num_requests + 1):
        request_id = 70000 + i
        created = START_DATE + timedelta(
            minutes=random.randint(0, 120 * 24 * 60)
        )

        # The ID is hidden inside a free text message, not its own column.
        message = (
            f"Approval needed for request {request_id} submitted by "
            f"{random.choice(REQUESTERS)}. Please review."
        )
        requests.append({
            "row_id": i,
            "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        })

        # Most requests get a response; a few never do.
        if random.random() < 0.9:
            responded = random_datetime(created, max_days=7)
            resp_message = (
                f"Response to request {request_id}: approved by "
                f"{random.choice(RESPONDERS)}."
            )
            responses.append({
                "row_id": len(responses) + 1,
                "responded_at": responded.strftime("%Y-%m-%d %H:%M:%S"),
                "message": resp_message,
            })

            # Occasionally add a duplicate response (noise to be filtered).
            if random.random() < 0.08:
                responses.append({
                    "row_id": len(responses) + 1,
                    "responded_at": (responded + timedelta(seconds=2))
                        .strftime("%Y-%m-%d %H:%M:%S"),
                    "message": resp_message,
                })

        # Occasionally add a system generated noise row with no real request.
        if random.random() < 0.05:
            responses.append({
                "row_id": len(responses) + 1,
                "responded_at": (created + timedelta(minutes=1))
                    .strftime("%Y-%m-%d %H:%M:%S"),
                "message": "System notice: no request id. Automated entry.",
            })

    return requests, responses


def write_csv(filename, rows):
    fieldnames = list(rows[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    requests, responses = build_data(NUM_REQUESTS)
    write_csv("requests.csv", requests)
    write_csv("responses.csv", responses)
    print(f"Wrote {len(requests)} requests to requests.csv")
    print(f"Wrote {len(responses)} responses to responses.csv")


if __name__ == "__main__":
    main()
