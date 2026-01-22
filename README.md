# Project description
This is an AI agent that book user to service

Agent is working in agent loop. The main tools are:
- list_services
- list_records
- create_record

All data is placing in csv files:
- services.csv - this is information about services and their schedule
- records.csv - this is information of already booked slots

After starting the script there will be input for user

Possible user input cases:
- "what services you have?"
- "what slots I can book for haircut tomorrow?"
- "i want to book haircut from 9:00"


# Environment
OPENAI_API_KEY - it is your key for request to openai https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key