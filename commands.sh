## Invoke Lambda locally
sam local invoke clarvoDocumentProcessor --event scripts/textract-input.json > output.json 2>logs/textract.logs

## Update Lambda Function
./scripts/update-lambda.sh .