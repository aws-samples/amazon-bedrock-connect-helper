"""
The test script to run advanced feature tests

Examples of using BedrockConnectHelper to call Bedrock APIs:
- Converse
- ConverseStream
- InvokeModel
- InvokeModelWithResponseStream

Each section of the run_test function can be extracted to request a Bedrock API separately. 

The script usage:
usage: advanced_feature_tests.py [-h] api_name={converse,converse_stream,invoke_model,invoke_model_with_response_stream} debug_mode={1,0}
example:
python advanced_feature_tests.py converse 0
"""
import argparse
from bedrock_connect_helper import *

# Set the file path to the Bedrock endpoint configuration file
filename = 'bedrock_connect_helper/bedrock_endpoints.conf'

# Bedrock model ID
model_id = "anthropic.claude-3-haiku-20240307-v1:0"

def run_test(api_name, debug_mode):
    """Run test for sending requests to LLM API using BedrockConnectHelp"""

    # Tip: Change the value to run tests on different APIs
    valid_test_modes = ['converse', 'converse_stream', 'invoke_model', 'invoke_model_with_response_stream']
    
    if api_name in valid_test_modes:
        test_mode = api_name
    else:
        print("Invalid API name!\n")
        return False

    if debug_mode > 0:
        debug_mode = True
    else:
        debug_mode = False

    # Get BedrockConnectHelper instance
    bedrock_helper = BedrockConnectHelper(model_id=model_id, auto_load_config=True, auto_update_config=False, config_file_path=filename,
                                            debug_mode=debug_mode, api_read_timeout=1, api_connect_timeout=1)

    # Enable Amazon Bedrock Cross-region inference feature. Please note till 2024-09-14, it only supports some of Anthropic's Claude models.
    # bedrock_helper.set_cross_region_inference(True)

    # Test Bedrock Converse API
    if test_mode == 'converse':
        # Set inference configs
        inference_configs = {
                'maxTokens': 2000,
                'temperature': 0.5,
                'stopSequences': [
                    '</result>',
                ]
            }

        bedrock_helper.set_inference_config(inference_configs)

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

        # Send the Request
        response = bedrock_helper.bedrock_converse_with_retry(prompt, system_prompt, extract_content=True) # Converse API
        print("# BEDROCK Converse API:\n", response, "\n")

    elif test_mode == 'converse_stream':
        # Set inference configs
        inference_configs = {
                'maxTokens': 2000,
                'temperature': 0.5,
                'stopSequences': [
                    '</result>',
                ]
            }

        bedrock_helper.set_inference_config(inference_configs)

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

        # Send the Request
        response = bedrock_helper.converse_stream(messages=prompt, system=system_prompt) # ConverseStream API
        print("# BEDROCK Converse API:\n", response, "\n")

        if response:
            stream = bedrock_helper.extract_response()

            streaming_data = bedrock_helper.retrieve_response_stream()
            print("##STREAM DATA:\n", streaming_data)

    elif test_mode == 'invoke_model':
        import json

        message = [{"role":"user", "content": [{"type": "text", "text": "Say Hello"}]}]

        request_body = {
            "messages": message,
            "system": "",
            "max_tokens": 256,
            "anthropic_version": "bedrock-2023-05-31"
        }

        response = bedrock_helper.invoke_model(body=json.dumps(request_body)) # InvokeModel API
        print("# BEDROCK InvokeModel API:\n", response, "\n")
        
        if response:
            print("## CONTENT:\n", bedrock_helper.extract_response(), "\n")

    elif test_mode == 'invoke_model_with_response_stream':
        import json

        message = [{"role":"user", "content": [{"type": "text", "text": "Say Hello"}]}]

        request_body = {
            "messages": message,
            "system": "",
            "max_tokens": 256,
            "anthropic_version": "bedrock-2023-05-31"
        }

        response = bedrock_helper.invoke_model_with_response_stream(body=json.dumps(request_body)) # InvokeModelWithResponseStream API
        print("# BEDROCK InvokeModelWithResponseStream API:\n", response)

        if response:
            stream = bedrock_helper.extract_response()

            streaming_data = bedrock_helper.retrieve_response_stream()
            print("##STREAM DATA:\n", streaming_data)

    # Manually update Bedrock Endpoint Configuration File
    print('# FAILED REGIONS:', bedrock_helper.failed_regions)
    new_config = bedrock_helper.disable_region_in_conf()

    if new_config is not None:
        # Write the updated region configurations back to the bedrock_endpoints.conf
        conf_save_result = bedrock_helper.write_json_to_file_with_lock(new_config)


def main():
    parser = argparse.ArgumentParser(description='Main script')
    parser.add_argument('api_name', choices=['converse', 'converse_stream', 'invoke_model', 'invoke_model_with_response_stream'])
    parser.add_argument('debug_mode', choices=['1', '0'])
    args = parser.parse_args()

    run_test(args.api_name, int(args.debug_mode))

if __name__ == "__main__":
    main()
