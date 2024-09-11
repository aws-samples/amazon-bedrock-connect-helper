"""
An example of the calling Bedrock Converse API using BedrockConnectHelper

Modify the value of "debug_mode" parameter to switch on/off debug information,
when initialize the BedrockConnectHelper class instance.
"""
# import json
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

# Send the Request
response = bedrock_helper.converse(messages=prompt, system=system_prompt) # Converse API
print('# BEDROCK RESPONSE:', response)
print('# FAILED REGIONS:', bedrock_helper.failed_regions)

# Update Bedrock Endpoint Configuration File
new_config = bedrock_helper.disable_region_in_conf()

if new_config is not None:
    ## Write the updated region configurations back to the bedrock_endpoints.conf
    conf_save_result = bedrock_helper.write_json_to_file_with_lock(new_config)
