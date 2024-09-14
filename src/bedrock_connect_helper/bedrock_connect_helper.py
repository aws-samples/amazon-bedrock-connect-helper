"""
A helper class example for implementing Cross-Region Resilience Solution
This example class implements the Amazon Bedrock Cross-Region Resilience Solution using the AWS Python SDK (boto3).

Key configurations:
    MAX_RETRY_TIME (int) -- The maximum number of retry attempts for Bedrock APIs. Recommended values are 3-5.
    MULTI_REGION_RETRY (bool) -- Retry Bedrock APIs in multiple regions if APIs are temporarily unable to respond correctly.
    MAX_RETRY_TIMES_FOR_EACH_REGION (int) -- The maximum number of retry attempts for each region before trying a different region.
        The total max_retry_times_for_each_region cannot exceed max_retry_time.
    PRIMARY_REGION_RANDOM_DISTRIBUTION (bool) -- Randomly select one of primary regions for the initial API request and prioritize 
        primary regions over other regions when it is set to True.
    NEXT_RETRY_TIME_WINDOW (int) -- The time window (in seconds) added to the current time to set the next available time for failed endpoints.
    ENABLE_CROSS_REGION_INFERENCE (bool) - Whether use Amazon Bedrock cross-region inferece feature
"""
import json
import time
import os
import fcntl
import random
import boto3
import botocore

from .bedrock_connect_util import * # Import the BedrockConnectUtil classes

class BedrockConnectHelper:

    # Global configurations
    MAX_RETRY_TIME = 5
    NEXT_RETRY_TIME_WINDOW = 3600  # 1 hour
    MULTI_REGION_RETRY = True
    MAX_RETRY_TIMES_FOR_EACH_REGION = 1
    PRIMARY_REGION_RANDOM_DISTRIBUTION = True
    ENABLE_CROSS_REGION_INFERENCE = False

    VALID_BEDROCK_APIS = ['converse', 'converse_stream', 'invoke_model', 'invoke_model_with_response_stream']

    # Shared attributes
    debug_mode = False
    api_method = 'converse'
    data_type = 'text'
    read_timeout = 5
    connect_timeout = 5

    # Bedrock API parameters
    accept = 'application/json'
    contentType = 'application/json'

    error_logs = []

    def __init__(self, model_id='', auto_load_config=True, auto_update_config=False, config_file_path='',
            debug_mode=False, api_read_timeout=5, api_connect_timeout=5):
        """
        Initialize an instance of the class
        
        Calcuate the current timestamp for process. Set customized parameters.
        Load the endpoint configuration file when the auto_load_config = True.

        Args:
            model_id (string) --  One of Amazon Bedrock model ids for inference.
            auto_load_config (bool) -- Allow the instance initialization to automatically load the endpoint configuration file or not.
            auto_update_config(bool) -- Allow the class destructor to automatically retrieve failed endpoints and update configuration file.
            config_file_path (string) -- Set a customized configuation file path.
            debug_mode (bool) -- Allow the debug() method to print out logs. 
            api_read_timeout (int) -- Set botocore.config.Config: read_timeout.
            api_connect_timeout (int) -- Set botocore.config.Config: connect_timeout.
        """
        # Calculate the current time for checking API endpoints' availability
        self.current_time = round(time.time())

        if model_id:
            self.model_id = model_id
        else:
            self.model_id = ''

        if config_file_path:
            self.config_file_path = config_file_path

        if debug_mode:
            self.debug_mode = debug_mode

        self.auto_update_config = auto_update_config

        self.raw_region_configs = []
        self.failed_regions = []
        self.response = {}
        self.bedrock_utilities = {}

        # Optional API parameters
        self.inferenceConfig = {}
        self.toolConfig = {}
        self.guardrailConfig = {}
        self.additionalModelRequestFields = None
        self.additionalModelResponseFieldPaths = []

        # Set customized config to botocore
        self.config = botocore.config.Config(
            read_timeout=api_read_timeout,
            connect_timeout=api_connect_timeout,
            retries={"max_attempts": 0}
        )

        # Load API endpoint automatically - endpoints are limited to each model instance
        if auto_load_config:
            self.debug(f"CONFIG_FILE_PATH: {config_file_path}")
            self.load_conf_file()

            ## Retrieve currently validate regions from the bedrock_endpoints.conf
            self.validate_regions = self.get_validate_regions_from_conf(self.raw_region_configs)


    def load_conf_file(self, file_path=''):
        """
        Load the Bedrock Endpoint Configuration File

        Args:
            file_path (string) -- Overwrite the default file path to the configuration file
        """
        if file_path:
            self.config_file_path = file_path
        
        filename = self.config_file_path

        try:
            with open(filename) as f:
                endpoint_config = f.read()

            self.raw_region_configs = json.loads(endpoint_config)
            
        except Exception as e:
            error_msg = f"Error: Load configuration file failed! {str(e)}"
            self.error_logs.append(error_msg)
            self.debug(error_msg)

        return self

    def get_validate_regions_from_conf(self, region_configs=[]):
        """
        Filter the list of endpoints to keep only the available endpoints in descending order
        based on each endpoint's next available time.

        When primary endpoints are set, prioritize primary endpoints.

        Args:
            region_configs (list) -- The list of endpoints, loaded from the "bedrock_endpoints" by default. Overwrite the list.

        Return:
            List
        """
        validate_regions = []
        primary_regions = []

        if not region_configs and hasattr(self, 'raw_region_configs'):
            region_configs = self.raw_region_configs

        for regional_conf in region_configs:
            self.debug('### REGION CONF:' + str(regional_conf))

            if regional_conf['next_available_time'] <= self.current_time:
                if self.PRIMARY_REGION_RANDOM_DISTRIBUTION and regional_conf['primary']:
                    primary_regions.append(regional_conf['region'])
                else:
                    validate_regions.append(regional_conf['region'])

        # Select one primary region randomly and add the primary regins to the front of the region list
        if self.PRIMARY_REGION_RANDOM_DISTRIBUTION and primary_regions:
            primary_region_num = len(primary_regions)

            if primary_region_num > 1:
                first_region_index = random.randrange(primary_region_num)
                
                first_region = primary_regions[first_region_index]
                primary_regions.pop(first_region_index)
                primary_regions.insert(0, first_region)

            validate_regions = primary_regions + validate_regions

        if validate_regions:
            self.validate_regions = validate_regions

        return validate_regions


    def set_cross_region_inference(self, enable_cross_region):
        self.ENABLE_CROSS_REGION_INFERENCE = enable_cross_region

        return self

    def set_api_method(self, api_method):
        """Set API method and create relevant Utility object"""
        if api_method and api_method in self.VALID_BEDROCK_APIS:
            self.api_method = api_method

            # Get instance of API utility class
            self.bedrock_utilities[self.api_method] = BedrockConnectUtilFactory.getInstance(apiMethod=self.api_method, debugMode=self.debug_mode)

        return self

    def set_model_id(self, model_id):
        if model_id:
            self.model_id = model_id
        
        return self

    def set_inference_config(self, configs, additional_configs=None):
        if configs:
            self.inferenceConfig = configs

        if additional_configs:
            self.additionalModelRequestFields = additional_configs

        return self

    def set_tool_config(self, tool_configs):
        if tool_configs:
            self.toolConfig = tool_configs

        return self

    def set_guardrail_config(self, guardrail_configs):
        if guardrail_configs:
            self.guardrail_configs = guardrail_configs

        return self


    def constract_api_kwargs(self, api_request_kwargs, api_method='', **kwargs):
        """
        Construct optional API arguments based on API method name

        Args:
            api_request_kwargs(dict) - Required API parameters
            api_method(str) - API method name: converse | invoke_model
            **kwargs(dict) - Optional arguments

        Returns:
            Dictionary: Extraction of specific item(s) or Original Required API parameters
        """

        if api_request_kwargs is None:
            self.debug("Invalid API PARAMS!\n")
            return api_request_kwargs

        if api_method:
            self.set_api_method(api_method)

        if self.api_method in ["converse", "converse_stream"]:
            # Pre-defined valid parameters of Bedrock Converse API
            attributes = ['inferenceConfig', 'toolConfig', 'guardrailConfig', 'additionalModelRequestFields', 'additionalModelResponseFieldPaths']

        elif self.api_method in ['invoke_model', 'invoke_model_with_response_stream']:
            attributes = ['contentType', 'accept', 'trace', 'guardrailIdentifier', 'guardrailVersion']

        # Iterate all optional parameter names and get their values
        for attr_name in attributes:
            instance_attribute = getattr(self, attr_name)
            self.debug(f"## INSTANCE ATTRIBUTE {attr_name}:\n{instance_attribute}")

            if instance_attribute:
                if api_request_kwargs is not None:
                    api_request_kwargs.update({attr_name: instance_attribute})
                else:
                    api_request_kwargs = {attr_name: instance_attribute}

        return api_request_kwargs

    def extract_response(self, key='content', depth=2):
        """Extract an attribute from LLM response JSON
        Args:
            api_method(string): Converse API or InvokeModel API
            streaming(bool):
            key (string): Attribute name to extract; enum [content, usage]
            depth (int): 
        """
        output = None

        if self.response is not None:

            if self.api_method == 'converse':

                if (key == 'content' and 'output' in self.response
                    and 'message' in self.response['output']):
                    # Retrieve Content
                    output = self.response['output']['message'][key]
                elif key == 'usage' and key in self.response:
                    output = self.response[key]
            
            elif self.api_method == 'converse_stream':
                output = self.response.get('stream')
                self.stream_data = output
                depth = 0

            elif self.api_method == 'invoke_model':
                output = json.loads(self.response.get('body').read())[key]

            elif self.api_method == "invoke_model_with_response_stream":
                output = self.response.get('body')
                self.stream_data = output
                depth = 0
        
        if output is not None:
            if depth == 1:
                output = output[0]
            elif depth == 2:
                output = output[0][self.data_type]

        return output


    def retrieve_response_stream(self, contentOnly=True):
        """Retriev streaming response data"""
        output = ''

        if self.stream_data:

            if self.api_method: # Use BedrockConnectUtil object
                bedrock_util = self.bedrock_utilities[self.api_method]
                stream_data = bedrock_util.retrieve_response_stream_chunk(self.stream_data, contentOnly)
                self.debug(f"## Stream data:\n{stream_data}")

                if stream_data:
                    output = self.bedrock_utilities[self.api_method].retrieve_response_streamdata(stream_data, contentOnly)
        
        return output


    def bedrock_converse_with_retry(self, messages, system=[], extract_content=False):
        """
        Send a request to Amazon Bedrock Converse API and retry according to related configurations
        when API request does not return a valid response.
        
        Args:
            messages (list): Prompts for Bedrock API request.
            system (list): System prompts.
            extract_content (bool): Return the raw API response when given False. Only return the "content" when given True.
        """
        output = False

        if not messages:
            error_msg = 'Argument "messages" is invalid!'
            self.error_logs.append(error_msg)
            self.debug(error_msg)

            return False

        if not self.validate_regions:
            error_msg = 'No available endpoint!'
            self.error_logs.append(error_msg)
            self.debug(error_msg)

            return False

        retry_time = 0
        model_id = self.model_id # Need a runtime model_id because of Bedrock cross-region inference profile ID.

        for region_name in self.validate_regions: # Loop through available endpoints until configured exit criteria is met.

            if region_name is not None and retry_time < self.MAX_RETRY_TIME:
                region_profile_prefix = ''

                bedrock = boto3.client('bedrock-runtime', region_name=region_name, config=self.config) # Initialize a regional Bedrock client

                # Assign the bedrock method to a variable
                call_bedrock_runtime_api = getattr(bedrock, self.api_method)
                self.debug(f"\n# Use region: {region_name} via API {self.api_method}\n")

                # Construct Bedrock Cross-region inference profile ID
                if self.ENABLE_CROSS_REGION_INFERENCE:
                    region_profile_prefix = next((regional_data['region_profile_prefix'] for regional_data in self.raw_region_configs if regional_data['region'] == region_name), None)

                    if region_profile_prefix:
                        model_id = region_profile_prefix + '.' + self.model_id
                    else:
                        self.debug(f"Failed to construct regional cross-region inference profile ID!\n")

                for one_region_retry_time in range(self.MAX_RETRY_TIMES_FOR_EACH_REGION):
                    # Retry the request to one region

                    if retry_time < self.MAX_RETRY_TIME:

                        try:

                            # Construct API arguments based on API method name
                            if self.api_method in ['converse', 'converse_stream']:

                                llm_api_kwargs = {
                                    'modelId': model_id,
                                    'messages': messages,
                                    'system': system
                                }

                            elif self.api_method in ['invoke_model', 'invoke_model_with_response_stream']:

                                llm_api_kwargs = {
                                    'modelId': model_id,
                                    'body': messages,
                                }
                            else:
                                break # Better handle errors

                            # Add optional LLM API parameters based on the API name
                            llm_api_kwargs = self.constract_api_kwargs(llm_api_kwargs)
                            self.debug(f"## ADD API KWARGS:\n {llm_api_kwargs}\n")

                            # Call LLM API Bedrock Converse
                            if llm_api_kwargs is not None:
                                # Pass required parameters and optional parameters to the LLM API
                                response = call_bedrock_runtime_api(**llm_api_kwargs)
                            else:
                                self.debug(f"Failed! No valid parameters for the API request at LINE []!\n")
                                return False # @TODO: It should raise an exception

                            self.debug(f"Inference modelID: {model_id}")

                            if response:
                                self.response = response

                                if extract_content:
                                    return self.extract_response('content')
                                else:
                                    return response
                            else:
                                if one_region_retry_time == 0:
                                    self.failed_regions.append(region_name) # Add the region to the failed region list

                                retry_time += 1
                                continue
                        except (bedrock.exceptions.ValidationException, botocore.exceptions.ParamValidationError) as e:
                            """ Do not add endpoints to failed regions for ValidationException or ParamValidationError,
                                to prevent from unexpected removing all available endpoints.
                            """
                            error_msg = f"ERROR: Invoke '{model_id}' error. Reason: {e}"
                            self.error_logs.append(error_msg)
                            self.debug(error_msg)

                            retry_time += 1

                            continue
                        except (botocore.exceptions.ClientError, Exception) as e:
                            error_msg = f"ERROR: Can't invoke '{model_id}'. Reason: {e}"
                            self.error_logs.append(error_msg)
                            self.debug(error_msg)
                            
                            if one_region_retry_time == 0:
                                self.failed_regions.append(region_name) # Add the region to the failed region list

                            retry_time += 1
                            continue
                    else:
                        break
            else:
                break

        return False


    def converse(self, messages, system=[], modelId='', inferenceConfig={},
            toolConfig={}, guardrailConfig={}, additionalModelRequestFields=None,
            additionalModelResponseFieldPaths=[]):
        """A mask method of BedrockRuntime.Client.converse()

            Doc: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html
        """
        output = None

        if not messages:
            return output

        self.set_api_method('converse')

        if modelId:
            self.set_model_id(modelId)

        if inferenceConfig:
            self.set_inference_config(inferenceConfig, additionalModelRequestFields)

        if toolConfig:
            self.set_tool_config(toolConfig)

        if guardrailConfig:
            self.set_guardrail_config(guardrailConfig)

        return self.bedrock_converse_with_retry(messages, system=system)


    def converse_stream(self, messages, system=[], modelId='', inferenceConfig={},
            toolConfig={}, guardrailConfig={}, additionalModelRequestFields=None,
            additionalModelResponseFieldPaths=[]):
        """A mask method of BedrockRuntime.Client.converse_stream()

            Doc: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse_stream.html
        """

        output = None

        self.set_api_method('converse_stream')

        if not messages:
            return output

        if modelId:
            self.set_model_id(modelId)

        if inferenceConfig:
            self.set_inference_config(inferenceConfig, additionalModelRequestFields)

        if toolConfig:
            self.set_tool_config(toolConfig)

        if guardrailConfig:
            self.set_guardrail_config(guardrailConfig)

        return self.bedrock_converse_with_retry(messages, system=system)


    def invoke_model(self, body, modelId='', **kwargs):
        """A mask method of BedrockRuntime.Client.invoke_mode()

            Doc: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model.html
        """
        output = None

        self.set_api_method('invoke_model')

        if not body:
            return output

        if modelId:
            self.model_id = modelId
        
        if 'contentType' in kwargs:
            self.contentType = kwargs['contentType']

        if 'accept' in kwargs:
            self.accept = kwargs['accept']

        if 'trace' in kwargs and kwargs['trace'] == 'ENABLED':
            self.trace = trace
        else:
            self.trace = 'DISABLED'

        if 'guardrailIdentifier' in kwargs:
            self.guardrailIdentifier = kwargs['guardrailIdentifier']
        else:
            self.guardrailIdentifier = None

        if 'guardrailVersion' in kwargs:
            self.guardrailVersion = kwargs['guardrailVersion']
        else:
            self.guardrailVersion = None

        return self.bedrock_converse_with_retry(messages=body)


    def invoke_model_with_response_stream(self, body, modelId='', **kwargs):
        """A mask method of BedrockRuntime.Client.invoke_mode_with_response_stream()

            Doc: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model_with_response_stream.html
        """
        output = None

        self.set_api_method('invoke_model_with_response_stream')

        if not body:
            return output

        if modelId:
            self.model_id = modelId
        
        if 'contentType' in kwargs:
            self.contentType = kwargs['contentType']

        if 'accept' in kwargs:
            self.accept = kwargs['accept']

        if 'trace' in kwargs and kwargs['trace'] == 'ENABLED':
            self.trace = trace
        else:
            self.trace = 'DISABLED'

        if 'guardrailIdentifier' in kwargs:
            self.guardrailIdentifier = kwargs['guardrailIdentifier']
        else:
            self.guardrailIdentifier = None

        if 'guardrailVersion' in kwargs:
            self.guardrailVersion = kwargs['guardrailVersion']
        else:
            self.guardrailVersion = None

        return self.bedrock_converse_with_retry(messages=body)


    def disable_region_in_conf(self, disable_regions=[]):
        """
        Set the next available timestamp to disable a region in the configuration file

        Args:
            self.raw_region_configs (dict): The raw list of Bedrock endpoints from the "bedrock_endpoints" file.
            disable_regions (list): The endpoints to be calculated and set next available time.
        """
        # Calcuate failed endpoints' next available time
        next_timestamp = self.current_time + self.NEXT_RETRY_TIME_WINDOW
        self.debug(f"## NEXT AVAILABLE TIME: {next_timestamp}")

        if not disable_regions:
            disable_regions = self.failed_regions

        disable_count = len(disable_regions)

        if disable_count == 0:
            self.debug('No need to update bedrock_endpoints.conf')
            return None

        for region_data in self.raw_region_configs:
            if region_data['region'] in disable_regions:
                region_data['next_available_time'] = next_timestamp

        return self.raw_region_configs


    def write_json_to_file_with_lock(self, data):
        """
        Overwrite the Bedrock endpoint configuration file with file locking to handle concurrent writes.

        Args:
            self.config_file_path (str): The path to the Bedrock endpoint configuration file where the JSON data will be written.
            data (list): The JSON data to write to the file.
        """
        if not data:
            self.debug("JSON configurations are invalid!")
            return False

        # Convert the Python dictionary to a JSON string
        json_data = json.dumps(data)

        try:
            with open(self.config_file_path, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # Acquire an exclusive lock on the file
                f.write(json_data)
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)  # Unlock the file

            return True

        except IOError as e:
            self.debug(f"Error writing to file: {e}")
            return False


    def __del__(self):
        """
        Class Destructor
        
        Retrieve all failed endpoints and update next_available_time to them,
        when the object is destroyed.
        """
        if not self.auto_update_config:
            return

        # Update Bedrock Endpoint Configuration File
        new_config = self.disable_region_in_conf()

        if new_config is not None:
            ## Write the updated region configurations back to the bedrock_endpoints.conf
            conf_save_result = self.write_json_to_file_with_lock(new_config)


    def set_debug_mode(self, status=False):
        """Switch the debug mode on/off."""
        self.debug_mode = status

        return self

    def debug(self, message):
        """Print debug messaging in debug mode."""
        if self.debug_mode:
            print(message)
