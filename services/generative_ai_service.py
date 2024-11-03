import json

import websockets

class GenerativeAIServiceClient:
    """Client for connecting to the generative audio microservice via WebSocket."""

    def __init__(self, uri: str):
        self.uri = uri
        self.websocket = None 

    async def connect(self):
        """Establish the WebSocket connection."""
        self.websocket = await websockets.connect(self.uri)
        print(f"Connected to WebSocket at {self.uri}")

    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("WebSocket connection closed")

    async def request_generate_voice(self, text: str, reference_audio: str) -> str:
        """Send a request to generate audio and wait for the response."""
        if not self.websocket:
            raise ConnectionError("WebSocket is not connected")

        # Send the request to generate audio
        message = {
            "type": "generate_voice",
            "text": text,
            "reference_audio": reference_audio
        }
        await self.websocket.send(json.dumps(message))

        # Wait for the response with the audio URL
        while True:
            response = await self.websocket.recv()
            data = json.loads(response)

            if data["type"] == "generated_voice_url":
                return data["content"]  # Return the audio URL
            elif data["type"] == "error":
                raise Exception(f"Error: {data['content']}")
