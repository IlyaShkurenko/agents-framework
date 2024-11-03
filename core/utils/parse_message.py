import json


def parse_message(message):
    try:
        base_string = "Use these arguments to process your task:"
        if base_string in message:
            json_data = message.split(base_string)[1].strip()
            arguments = json.loads(json_data)
            seed_image = None
            prompt = None

            for arg in arguments:
                if arg["name"] == "prompt":
                    prompt = arg["value"]
                elif arg["name"] == "seed_image":
                    seed_image = arg["value"]
            
            return seed_image, prompt or message.strip()
        
        else:
            return None, message.strip()
    except (json.JSONDecodeError, IndexError, KeyError):
        return None, message.strip()