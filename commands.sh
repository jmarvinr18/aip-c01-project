## Invoke Lambda locally [with AWS Textract]
sam local invoke clarvoDocumentProcessor --event scripts/textract-input.json > output.json 2>logs/textract.logs


## Invoke Lambda locally [with AWS Rekognition]
sam local invoke clarvoDocumentProcessor --event scripts/rekognition-input.json > output.json 2>logs/rekognition.logs


## Invoke Lambda locally [with AWS Transcribe]
sam local invoke clarvoDocumentProcessor --event scripts/transcribe-input.json > output.json 2>logs/transcribe.logs

## Invoke Lambda locally for testing Agent Retriever
sam local invoke ClarvoBedrockAgentRetriever --event scripts/bedrock-agent-retriever.json > output.json 2>logs/ba_retriever.logs

## Invoke Lambda locally for Syncing Knowledge Base
sam local invoke clarvoKBSync > output.json 2>logs/ba_retriever.logs

## Invoke Lambda locally for Chat Stream
sam local invoke clarvoChatStream > output.json 2>logs/chat_stream.logs

## Update Lambda Function
./scripts/update-lambda.sh .


## Login to CodeArtifact
aws codeartifact login --tool pip --repository pypi-store --domain xctuality --domain-owner 408897322877 --region ap-southeast-1