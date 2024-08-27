# Amazon Bedrock Connect Helper
This repository contains samples of the implementation of the Amazon Bedrock Dynamic Cross-Region Routing Helper class to improve generative AI applications' resilience using the AWS SDK for Python (boto3).


## Get Started
### Prerequisites
- An [AWS account](https://aws.amazon.com/).
- Access to Bedrock and Claude 3 Haiku model in your AWS regions.
- Amazon IAM Role set up with sufficient permissions to access Amazon Bedrock. For details, see [IAM policy](https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam.html)
- Sufficient limits of Bedrock Requests Per Minute (RPM) and Tokens Per Minute (TPM) in all regions listed in your [bedrock_endpoints.conf](code/bedrock_endpionts.conf) file.
- An Amazon EC2 instance or deployment environment with the assigned IAM Role.
- AWS SDK for Python (boto3) installed on the Amazon EC2 instance or deployment environment.

### Run the demo
1. **Clone the repository**
```bash
git clone "https://github.com/aws-samples/amazon-bedrock-connect-helper.git"

cd amazon-bedrock-connect-helper/src
```

2. **Install and/or update required Python packages**

    Note: boto3 should be pre-installed on Amazon EC2 instances with Amazon Linux 2 AMI.

```bash
pip install -r requirements.txt
```

3. **Execute the test script**
    
    Note: Python 3.x installation may be called `python3` rather than `python`.
```bash
python main.py

# Expected response:
# BEDROCK RESPONSE: {'ResponseMetadata': {'RequestId': 'xxxxxx-xxxx-xxxx-xxxx-xxxxxxx', 'HTTPStatusCode': 200, 'HTTPHeaders': {'date': 'Tue, 27 Aug 2024 12:45:36 GMT', 'content-type': 'application/json', 'content-length': '185', 'connection': 'keep-alive', 'x-amzn-requestid': 'xxxxxx-xxxx-xxxx-xxxx-xxxxxxx'}, 'RetryAttempts': 0}, 'output': {'message': {'role': 'assistant', 'content': [{'text': 'Hello!'}]}}, 'stopReason': 'end_turn', 'usage': {'inputTokens': 9, 'outputTokens': 5, 'totalTokens': 14}, 'metrics': {'latencyMs': 259}}
# FAILED REGIONS: []
```

## Directories
```
./src/
  |- main.py # test script
  |- bedrock_connect_helper/
    |- bedrock_connect_helper.py # BedrockConnectHelper class
    |- bedrock_endpoints.conf # An example of the list of endpoints
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
