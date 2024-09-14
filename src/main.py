"""
An example of the calling Bedrock Converse API using BedrockConnectHelper

Modify the value of "debug_mode" parameter to switch on/off debug information,
when initialize the BedrockConnectHelper class instance.
"""
from bedrock_connect_helper.bedrock_connect_helper import BedrockConnectHelper

# Set the file path to the Bedrock endpoint configuration file
filename = 'bedrock_connect_helper/bedrock_endpoints.conf'

model_id = "anthropic.claude-3-haiku-20240307-v1:0"

# Construct a Bedrock InvokeModel API request
system_prompt = []

prompt = [
    {
        "role": "user",
        "content": [
            {
                "text": "Say Hello"
            }
        ]
    }
]

bedrock_helper = BedrockConnectHelper(model_id=model_id, auto_load_config=True, config_file_path=filename, debug_mode=False)

# Uncomment the line below to enable Amazon Bedrock Cross-region inference feature. Please note till 2024-09-14, it only supports some of Anthropic's Claude models.
# bedrock_helper.set_cross_region_inference(True)

# Send the Request
response = bedrock_helper.converse(messages=prompt, system=system_prompt) # Converse API
print('# BEDROCK RESPONSE:', response)
print('# FAILED REGIONS:', bedrock_helper.failed_regions)
