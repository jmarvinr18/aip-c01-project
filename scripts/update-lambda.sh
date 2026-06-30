#!/bin/bash

zip clarvo_document_processor.zip clarvo_document_processor.py

export AWS_PROFILE=408897322877_AdministratorAccess

aws s3 cp clarvo_document_processor.zip s3://aip-c01-bucket/lambda/

aws s3 ls s3://aip-c01-bucket/lambda/

ls -la
aws lambda update-function-code \
    --function-name "clarvoDocumentProcessor" \
    --s3-bucket "aip-c01-bucket" \
    --s3-key "lambda/clarvo_document_processor.zip" \
    --log-type Tail \
    --query 'LogResult' \
    --output text | base64 --decode \
    --region ap-southeast-1
