import csv
from datetime import datetime
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

def parse_slot(slot: str)-> Dict:
    date_str, time_range = slot.split(" ")
    start_time_str, end_time_str = time_range.split("-")
    start = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
    return {
        start: start,
        end: end
    }

def check_is_slots_intersect(slot1: Dict, slot2: Dict) -> bool:
    return slot1["from"] < slot2["to"] and slot2["from"] < slot1["to"]

def check_if_record_booked(record: Dict) -> bool:
    slot  = parse_slot(record["slot"])
    with open(RECORDS_FILE, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["service_id"] == record["service_id"] and check_is_slots_intersect(parse_slot(row["slot"]), slot):
                return True
    return False

if __name__ == '__main__':

    userInput = input("How can I help you?")

    agent_rules = [
        {
            "role":"system",
            "content": """
            You are a booking agent. You record users to services and help them to know what services they can book and what time.
            
            Available tools:
            - list_services() -> List[Dict]: List all services available
              the Dict is following fields and types: 
              service_id: int - id of the service
              name: str - the name of the service
              employee_name: str - the name of employee who will do the service
              schedule: str - the time when you can book the service. Format 2026-02-01 09:00-13:00 14:00-16:00|2026-02-02 10:00-14:00. UTC+3 timezone
              duration: int - duration of the service in minutes
              
            - list_records() -> List[Dict]: List all already booked records and their slots
              the Dict is following fields and types: 
              user_id: str - the user id. Format: uuid
              service_id: int - id of the service that user was booked
              slot: str - booked time slot. Format: 2026-02-01 09:00-09:30. UTC+3 timezone
              
            - create_record(record: Dict): Record user to service
              the record: Dict is following fields and types: 
              service_id: int - id of the service that user will book. Get from list_services result
              slot: str - time slot for booking. Format: 2026-02-01 09:00-09:30. UTC+3 timezone. 
            
            - terminate(message: str): End the agent loop and print summary to the user
              
              
              How to find out what slot to book? Get the schedule and the duration of service what you want to book from list_services
              Get all already booked records to this service from list_records
              Calculate where is a free time in schedule that not intersects with booked slots from list_records
              
              When you has a result for user question - always terminate the loop and send result to the message
              When user asks not about services or booking - terminate
              
              Every response MUST have an action.
              Respond in this format:
                
              ```action
              {
                "tool_name": "insert tool_name",
                "args": {...fill in any required arguments here...}
              }
        """}
    ]
    memory = []
    memory.append({
        "role": "user",
        "content": userInput
    })

    iterations = 1
    while iterations <= MAX_ITERATIONS:
        prompt = agent_rules + memory

        agent_response = generate_response(prompt)
        print(f"Agent response: {agent_response}")

        action = parse_action(agent_response)

        match action["tool_name"]:
            case "list_services":
                tool_result = {"result": list_services()}
            case "list_records":
                tool_result = {"result": list_records()}
            case "create_record":
                record = action["args"]
                create_record(record)
                tool_result = {"result": "Record created"}
            case "error":
                tool_result = {"error": action["args"]["message"]}
            case "terminate":
                print(action["args"]["message"])
                break
            case _:
                tool_result = {"error": f"Unknown action: {action['tool_name']}"}

        memory.extend([
            {
                "role": "assistant",
                "content": agent_response
            },
            {
                "role": "user",
                "content": json.dumps(tool_result)
            }
        ])

        iterations+=1

