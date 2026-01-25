import csv
import uuid
from datetime import datetime
import json
from os import terminal_size

from dotenv import load_dotenv
from litellm import completion
from typing import List, Dict, Optional
import os

from litellm.types.utils import Message

MAX_ITERATIONS = 10
SERVICES_FILE = "services.csv"
RECORDS_FILE = "records.csv"

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")


def generate_response(messages: List[Dict], tool_items: Optional[List] = None) -> Message:
    """Call LLM to get response"""
    response = completion(
        model="openai/gpt-4o",
        messages=messages,
        max_tokens=1024,
        tools=tool_items
    )
    return response.choices[0].message

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

def create_record(service_id: int, slot: str):
    check_if_record_booked(service_id, slot)

    fieldnames = ["user_id", "service_id", "slot"]
    with open("records.csv", mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow(
            {
                "user_id": uuid.uuid4(),
                "service_id": service_id,
                "slot": slot
            }
        )

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

def check_if_record_booked(service_id: int, slot: str) -> bool:
    slot  = parse_slot(slot)
    with open(RECORDS_FILE, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["service_id"] == service_id and check_is_slots_intersect(parse_slot(row["slot"]), slot):
                return True
    return False


#record me to haircut with Anna 2026-02-01 at 10:00
if __name__ == '__main__':

    userInput = input("How can I help you?")

    agent_rules = [
        {
            "role":"system",
            "content": """
            You are a booking agent. You record users to services and help them to know what services they can book and what time.
            To achieve that you can use available tools
              
              
              How to find out what slot to book? Get the schedule and the duration of service what you want to book from list_services
              Get all already booked records to this service from list_records
              Calculate where is a free time in schedule that not intersects with booked slots from list_records
              
              In response you MUST ALWAYS return one of the tools.
              When you done, terminate the conversation, using "terminate" tool and put your content to the message arg.
              If user question not about services or booking or you have no idea what about - response with "terminate" tool with your message instead of content
        """}
    ]
    memory = []
    memory.append({
        "role": "user",
        "content": userInput
    })

    tool_functions = {
        "list_services": list_services,
        "list_records": list_records,
        "create_record": create_record
    }

    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_services",
                "description": "List all services available",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "returns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "service_id": {
                                "type": "integer",
                                "description": "ID of the service"
                            },
                            "name": {
                                "type": "string",
                                "description": "Name of the service"
                            },
                            "employee_name": {
                                "type": "string",
                                "description": "Name of the employee who will perform the service"
                            },
                            "schedule": {
                                "type": "string",
                                "description": "Available booking times. Format: YYYY-MM-DD HH:MM-HH:MM [HH:MM-HH:MM]|YYYY-MM-DD HH:MM-HH:MM. Timezone UTC+3. Example: 2026-02-01 09:00-13:00 14:00-16:00|2026-02-02 10:00-14:00"
                            },
                            "duration": {
                                "type": "integer",
                                "description": "Duration of the service in minutes"
                            }
                        },
                        "required": [
                            "service_id",
                            "name",
                            "employee_name",
                            "schedule",
                            "duration"
                        ]
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_records",
                "description": "List all already booked records and their slots",
                "parameters": {},
                "returns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User identifier in UUID format"
                            },
                            "service_id": {
                                "type": "integer",
                                "description": "ID of the service that the user booked"
                            },
                            "slot": {
                                "type": "string",
                                "description": "Booked time slot. Format: YYYY-MM-DD HH:MM-HH:MM. Timezone UTC+3. Example: 2026-02-01 09:00-09:30"
                            }
                        },
                        "required": [
                            "user_id",
                            "service_id",
                            "slot"
                        ]
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_record",
                "description": "Record user to service",
                "parameters": {
                    "type": "object",
                    "properties": {
                      "service_id": {
                        "type": "integer",
                        "description": "ID of the service the user wants to book. Must be taken from the list_services tool result"
                      },
                      "slot": {
                        "type": "string",
                        "description": "Time slot for booking. Format: YYYY-MM-DD HH:MM-HH:MM. Timezone UTC+3. Example: 2026-02-01 09:00-09:30"
                      }
                    },
                    "required": ["service_id", "slot"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "terminate",
                "description": "End the agent loop and print summary to the user",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to display"
                        }
                    }
                }
            }
        }
    ]

    iterations = 1
    while iterations <= MAX_ITERATIONS:
        prompt = agent_rules + memory

        try:
            agent_response = generate_response(prompt, tools)
            tool = agent_response.tool_calls[0]
            tool_name = tool.function.name
            tool_args = json.loads(tool.function.arguments)
        except Exception as e:
            result = {"error": str(e)}
            continue

        print(f"Tool name: {tool_name}")
        print(f"Tool args: {tool_args}")

        if tool_name == "terminate":
            print(f"Termination message: {tool_args['message']}")
            break
        elif tool_name in tool_functions:
            try:
                match tool_name:
                    case 'create_record':
                        create_record(tool_args['service_id'], tool_args['slot'])
                        result = {"result": "Record created successfully"}
                    case _:
                        result = {"result": tool_functions[tool_name](**tool_args)}

            except Exception as e:
                result = {"error": str(e)}
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        print(f"Result: {result}")

        memory.extend([
            {
                "role": "assistant",
                "content": json.dumps({
                    "tool_name": tool_name,
                    "args": tool_args,
                })
            },
            {
                "role": "user",
                "content": json.dumps(result)
            }
        ])

        iterations+=1

