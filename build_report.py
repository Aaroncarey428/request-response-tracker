"""
build_report.py

Builds a turnaround report from messy request and response data:
  1. Extract the request ID from free text using regex
  2. Match each request to its earliest valid response
  3. Filter duplicates and system generated noise
  4. Calculate turnaround counting business hours only
  5. Flag anomalies (unusually fast or slow)
  6. Write a multi sheet Excel report

All data is synthetic. No real or proprietary information is used.

Usage:
    python generate_synthetic_data.py   (first, to create the CSVs)
    python build_report.py
"""

import os
import re
from datetime import datetime, timedelta

import pandas as pd

REQUESTS_FILE = "requests.csv"
RESPONSES_FILE = "responses.csv"
OUTPUT_DIR = "sample_output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "turnaround_report.xlsx")

# Business hours definition: 8 AM to 5 PM, Monday to Friday.
BUSINESS_START_HOUR = 8
BUSINESS_END_HOUR = 17
WORK_DAYS = {0, 1, 2, 3, 4}  # Monday=0 ... Friday=4


# ---------------------------------------------------------------------------
# 1. Extract the request ID from free text using a regular expression.
# ---------------------------------------------------------------------------
def extract_request_id(text):
    # Looks for the word "request" followed by a number.
    match = re.search(r"request (\d+)", str(text), re.IGNORECASE)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# 2. Business hours elapsed time between two datetimes.
#    Counts only time inside working hours on weekdays.
# ---------------------------------------------------------------------------
def business_hours_between(start, end):
    if end <= start:
        return 0.0

    total_seconds = 0.0
    current = start

    while current < end:
        # Define this day's business window.
        day_start = current.replace(
            hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
        )
        day_end = current.replace(
            hour=BUSINESS_END_HOUR, minute=0, second=0, microsecond=0
        )

        if current.weekday() in WORK_DAYS:
            # The overlap between [current, end] and this day's window.
            window_start = max(current, day_start)
            window_end = min(end, day_end)
            if window_end > window_start:
                total_seconds += (window_end - window_start).total_seconds()

        # Move to the start of the next day.
        next_day = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        current = next_day

    return round(total_seconds / 3600.0, 2)  # hours


# ---------------------------------------------------------------------------
# 3. Load, extract IDs, and filter noise.
# ---------------------------------------------------------------------------
def load_and_prepare():
    requests = pd.read_csv(REQUESTS_FILE, parse_dates=["created_at"])
    responses = pd.read_csv(RESPONSES_FILE, parse_dates=["responded_at"])

    requests["request_id"] = requests["message"].apply(extract_request_id)
    responses["request_id"] = responses["message"].apply(extract_request_id)

    # Filter system noise: responses with no extractable request ID.
    responses = responses.dropna(subset=["request_id"])
    responses["request_id"] = responses["request_id"].astype(int)
    requests["request_id"] = requests["request_id"].astype(int)

    # Remove duplicate responses: keep the earliest per request.
    responses = (
        responses.sort_values("responded_at")
        .drop_duplicates(subset=["request_id"], keep="first")
    )
    return requests, responses


# ---------------------------------------------------------------------------
# 4. Match requests to responses and compute turnaround.
# ---------------------------------------------------------------------------
def build_matched(requests, responses):
    merged = requests.merge(
        responses[["request_id", "responded_at"]],
        on="request_id", how="left"
    )

    # Business hours turnaround for matched rows.
    merged["turnaround_business_hours"] = merged.apply(
        lambda r: business_hours_between(r["created_at"], r["responded_at"])
        if pd.notnull(r["responded_at"]) else None,
        axis=1
    )
    merged["status"] = merged["responded_at"].apply(
        lambda x: "Responded" if pd.notnull(x) else "No response"
    )
    return merged


# ---------------------------------------------------------------------------
# 5. Flag anomalies using simple statistical thresholds.
# ---------------------------------------------------------------------------
def flag_anomalies(matched):
    responded = matched[matched["status"] == "Responded"].copy()
    if responded.empty:
        matched["anomaly"] = ""
        return matched

    mean = responded["turnaround_business_hours"].mean()
    std = responded["turnaround_business_hours"].std()
    high = mean + 2 * std

    def label(row):
        if row["status"] != "Responded":
            return ""
        if row["turnaround_business_hours"] >= high:
            return "Unusually slow"
        if row["turnaround_business_hours"] <= 0.1:
            return "Unusually fast"
        return ""

    matched["anomaly"] = matched.apply(label, axis=1)
    return matched


# ---------------------------------------------------------------------------
# 6. Write the multi sheet Excel report.
# ---------------------------------------------------------------------------
def write_report(matched):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    responded = matched[matched["status"] == "Responded"]

    summary = pd.DataFrame({
        "Metric": [
            "Total requests",
            "Responded",
            "No response",
            "Average turnaround (business hours)",
            "Median turnaround (business hours)",
            "Anomalies flagged",
        ],
        "Value": [
            len(matched),
            int((matched["status"] == "Responded").sum()),
            int((matched["status"] == "No response").sum()),
            round(responded["turnaround_business_hours"].mean(), 2),
            round(responded["turnaround_business_hours"].median(), 2),
            int((matched["anomaly"] != "").sum()),
        ],
    })

    detail = matched[[
        "request_id", "created_at", "responded_at",
        "turnaround_business_hours", "status", "anomaly"
    ]].sort_values("created_at")

    anomalies = detail[detail["anomaly"] != ""]

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        detail.to_excel(writer, sheet_name="Detail", index=False)
        anomalies.to_excel(writer, sheet_name="Anomalies", index=False)

    print(f"Wrote report to {OUTPUT_FILE}")
    print(f"  Requests: {len(matched)}, Responded: {len(responded)}, "
          f"Anomalies: {len(anomalies)}")


def main():
    if not (os.path.exists(REQUESTS_FILE) and os.path.exists(RESPONSES_FILE)):
        raise SystemExit(
            "Input CSVs not found. Run: python generate_synthetic_data.py first."
        )
    requests, responses = load_and_prepare()
    matched = build_matched(requests, responses)
    matched = flag_anomalies(matched)
    write_report(matched)


if __name__ == "__main__":
    main()
