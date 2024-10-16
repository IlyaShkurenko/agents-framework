#!/bin/bash

# export OPENAI_API_KEY='your_openai_api_key_here'
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
