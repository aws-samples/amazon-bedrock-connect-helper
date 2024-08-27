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
"""
import json
import time
import os
import fcntl
import random
import boto3
import botocore

class BedrockConnectHelper:

    # Global configurations
    MAX_RETRY_TIME = 5
    NEXT_RETRY_TIME_WINDOW = 3600  # 1 hour
    MULTI_REGION_RETRY = True
    MAX_RETRY_TIMES_FOR_EACH_REGION = 2
    PRIMARY_REGION_RANDOM_DISTRIBUTION = True

    # Shared attributes
    debug_mode = False
    api_method = 'converse'
    data_type = 'text'
    read_timeout = 900
    connect_timeout = 900

    # Bedrock API parameters
    accept = 'application/json'
    content_type = 'application/json'

    error_logs = []

    def __init__(self, model_id='', auto_load_config=True, config_file_path='', debug_mode=False, api_read_timeout=900, api_connect_timeout=900):
        """
        Initialize an instance of the class
        
        Calcuate the current timestamp for process. Set customized parameters.
        Load the endpoint configuration file when the auto_load_config = True.

        Args:
            model_id (string) --  One of Amazon Bedrock model ids for inference.
            auto_load_config (bool) -- Allow the instance initialization to automatically load the endpoint configuration file or not.
            config_file_path (string) -- Set a customized configuation file path.
            debug_mode (bool) -- Allow the debug() method to print out logs. 
            api_read_timeout (int) -- Set botocore.config.Config: read_timeout.
            api_connect_timeout (int) -- Set botocore.config.Config: connect_timeout.
        """
        # Calculate the current time for checking API endpoints' availability
        self.current_time = round(time.time())

        if model_id:
            self.model_id = model_id

        if config_file_path:
            self.config_file_path = config_file_path

        if debug_mode:
            self.debug_mode = debug_mode

        self.raw_region_configs = []
        self.failed_regions = []
        self.inferenceConfig = {}
        self.toolConfig = {}
        self.guardrailConfig = {}

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

    def bedrock_converse_with_retry(self, messages, system=[], extract_content=False):
        """
        Send a request to Amazon Bedrock Converse API and retry according to related configurations
        when API request does not return a valid response.
        
        Args:
            messages (list): Prompts for Bedrock API request.
            system (list): System prompts.
            extract_content (bool): Return the raw API response when given False. Only return the "content" when given True.
        """
        if not messages:
            error_msg = 'Argument "messages" is invalid!'
            self.error_logs.append(error_msg)
            self.debug(error_msg)

            return False

        if len(self.validate_regions) == 0:
            error_msg = 'No available endpoint!'
            self.error_logs.append(error_msg)
            self.debug(error_msg)

            return False

        retry_time = 0

        for region_name in self.validate_regions: # Loop through available endpoints until configured exit criteria is met.

            if region_name is not None and retry_time < self.MAX_RETRY_TIME:
                bedrock = boto3.client('bedrock-runtime', region_name=region_name, config=self.config) # Initialize a regional Bedrock client
                self.debug(f"Use region: {region_name}")

                for one_region_retry_time in range(self.MAX_RETRY_TIMES_FOR_EACH_REGION):
                    # Retry the request to one region

                    if retry_time < self.MAX_RETRY_TIME:

                        try:
                            response = bedrock.converse(modelId=self.model_id, messages=messages, system=system, inferenceConfig=self.inferenceConfig)

                            if response:
                                self.response = response

                                if extract_content and response['output']['message']['content'][0]:
                                    return response['output']['message']['content'][0]
                                else:
                                    return response
                            else:
                                if one_region_retry_time == 0:
                                    self.failed_regions.append(region_name) # Add the region to the failed region list

                                retry_time += 1
                                continue

                        except (botocore.exceptions.ClientError, Exception) as e:
                            error_msg = f"ERROR: Can't invoke '{self.model_id}'. Reason: {e}"
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

        if len(disable_regions) == 0:
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

    def set_debug_mode(self, status=False):
        """Switch the debug mode on/off."""
        self.debug_mode = status

        return self

    def debug(self, message):
        """Print debug messaging in debug mode."""
        if self.debug_mode:
            print(message)
