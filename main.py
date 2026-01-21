import csv
import datetime
import json

from dotenv import load_dotenv
from litellm import completion
from typing import List, Dict
import os

MAX_ITERATIONS = 10
SERVICES_FILE = "services.csv"
RECORDS_FILE = "records.csv"

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")


def generate_response(messages: List[Dict]) -> str:
    """Call LLM to get response"""
    response = completion(
        model="openai/gpt-4o",
        messages=messages,
        max_tokens=1024
    )
    return response.choices[0].message.content

def extract_markdown_block(response: str, block_type: str = "json") -> str:
    """Extract code block from response"""

    if not '```' in response:
        return response

    code_block = response.split('```')[1].strip()

    if code_block.startswith(block_type):
        code_block = code_block[len(block_type):].strip()

    return code_block

def parse_action(response: str) -> Dict[str, Dict]:
    try:
        response = extract_markdown_block(response, "action")
        response_json = json.loads(response)
        if "tool_name" in response_json and "args" in response_json:
            return response_json
        else:
            return {"tool_name": "error", "args": {"message": "You must respond with a JSON tool invocation."}}
    except json.JSONDecodeError:
        return {"tool_name": "error",
                "args": {"message": "Invalid JSON response. You must respond with a JSON tool invocation."}}

def list_services() -> List[Dict]:
    return read_csv_as_dict(SERVICES_FILE)

def list_records() -> List[Dict]:
    return read_csv_as_dict(RECORDS_FILE)

def read_csv_as_dict(path: str) -> List[Dict]:
    data = []
    with open(path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(dict(row))
    return data

def create_record(record: Dict):
    check_if_record_booked(record)

    fieldnames = ["service_id", "user_id", "slot"]
    with open("records.csv", mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow(record)

def parse_slot(slot: str)-> Dict[datetime, datetime]:
    date_str, time_range = slot.split(" ")
    start_time_str, end_time_str = time_range.split("-")
    start = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
    return {
        start: start,
        end: end
    }

def check_is_slots_intersect(slot1: Dict[datetime, datetime], slot2: Dict[datetime, datetime]) -> bool:
    return slot1["from"] < slot2["to"] and slot2["from"] < slot1["to"]

def check_if_record_booked(record: Dict) -> bool:
    slot  = parse_slot(record["slot"])
    with open(RECORDS_FILE, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["service_id"] == record["service_id"] & check_is_slots_intersect(parse_slot(row["slot"]), slot):
                return True
    return False

if __name__ == '__main__':

    agent_rules = [
        {"role":"system", "content": ""}
    ]
    memory = []
    iterations = 1
    while iterations <= MAX_ITERATIONS:
        prompt = agent_rules + memory

        agent_response = generate_response(prompt)
        print(f"Agent response: {agent_response}")

        action = parse_action(agent_response)


        iterations+=1

