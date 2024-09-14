"""
Utility classes for the sample of BedrockConnectHelper

They mainly provide methods to handle differences of various APIs.

BedrockConnectUtilFactory: A Factory class creates instance of a sub-class of BedrockConnectUtil.
BedrockConnectUtil: The parent utility class.
BedrockConnectUtilInvokeModel: A sub-class of BedrockConnectUtil class that provides data-handling methods for Bedrock InvokeModel & InvokeModelWithResponseStream APIs.
BedrockConnectUtilConverse: A sub-class of BedrockConnectUtil class that provides data-handling methods for Bedrock Converse & ConverseStream APIs.
"""
import botocore

class BedrockConnectUtilFactory:
    """
    A Factory class creates instance of a sub-class of BedrockConnectUtil

    Arguments:
        apiMethod(string) - The API name for creating relevant utility class.
    """

    def __init__(self, apiMethod=''):        
        self.api_method = apiMethod

    @staticmethod
    def getInstance(apiMethod, debugMode=False):
        """
        A static method to create the instance of relevant utility class
        
        Arguments:
            apiMethod(string) - The API name for choosing the relevant utility class.
            debugMode(bool) - It controls whether print debug information.
        
        Returns:
           Object - instance of the sub-class of BedrockConnectUtil
        """

        if "invoke_" in apiMethod:
            return BedrockConnectUtilInvokeModel(debugMode)
        else:
            return BedrockConnectUtilConverse(debugMode)


class BedrockConnectUtil:
    """
    The parent utility class that contains universal methods for all sub-classes

    Arguments:
        debugMode(bool) - It controls whether print debug information.
    """

    def __init__(self, debugMode=False):
        self.debug_mode = debugMode

        return None

    def set_debug_mode(self, status=False):
        """Switch the debug mode on/off."""
        self.debug_mode = status

        return self

    def debug(self, message):
        """Print debug messaging in debug mode."""
        if self.debug_mode:
            print(message)


    def retrieve_response_streamdata(self, streaming_data, contentOnly=True):
        """
        Retrieve data from streaming response as string

        Arguments:
            streaming_data(dict) - The object of the API streaming response.
            contentOnly(bool) - It controls whether retrieves the textual content only.

        Returns:
            Iterator
        """
        output = ''

        if streaming_data:

            while True:

                try:
                    chunk_data = next(streaming_data)

                    if contentOnly and 'text' in chunk_data:
                        output += str(chunk_data['text'])
                    else:
                        output += str(chunk_data)

                except botocore.exceptions.EventStreamError as e:
                    self.debug(f"Error processing event stream: {e}")
                    break
                except StopIteration:
                    break

        return output


class BedrockConnectUtilInvokeModel(BedrockConnectUtil):
    """
    The utility class that contains methods for Bedrock InvokeModel & InvokeModelWithResponseStream APIs

    Arguments:
        debugMode(bool) - It controls whether print debug information.
    """

    def retrieve_response_stream_chunk(self, stream_data, contentOnly=False):
        """
        Retrieve streaming response chunks

        Arguments:
            stream_data(dict) - The object of the API streaming response.
            contentOnly(bool) - It controls whether retrieves the textual content only.

        Returns:
            Iterator
        """
        import json

        if stream_data:
            for event in stream_data:
                
                chunk = event.get("chunk")

                if chunk:
                    chunk_obj = json.loads(chunk.get("bytes").decode())
                    self.debug(f"STREAMING INFO: {chunk_obj}\n")

                    if contentOnly:
                        if 'delta' in chunk_obj and 'text' in chunk_obj['delta']:
                            text = chunk_obj['delta']
                        else:
                            self.debug(f"STREAMING INFO: {chunk_obj}\n")
                            continue
                    else:
                        text = chunk_obj

                    yield text


class BedrockConnectUtilConverse(BedrockConnectUtil):
    """
    The utility class that contains methods for Bedrock Converse & ConverseStream APIs

    Arguments:
        debugMode(bool) - It controls whether print debug information.
    """

    def retrieve_response_stream_chunk(self, stream_data, contentOnly=False):
        """
        Retrieve streaming response chunks

        Arguments:
            stream_data(dict) - The object of the API streaming response.
            contentOnly(bool) - It controls whether retrieves the textual content only.

        Returns:
            Iterator
        """
        if stream_data:

            for event in stream_data:
                self.debug(f"STREAMING INFO: {event}\n")
                
                if contentOnly:
                    if 'contentBlockDelta' in event and 'delta' in event['contentBlockDelta']:
                        text = event['contentBlockDelta']['delta']
                    else:
                        continue
                else:
                    text = event

                yield text
