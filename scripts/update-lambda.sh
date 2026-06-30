#!/bin/bash

zip lambda_function.zip lambda_function.py

export AWS_PROFILE=408897322877_AdministratorAccess

aws s3 cp lambda_function.zip s3://aip-c01-bucket/lambda/

aws s3 ls s3://aip-c01-bucket/lambda/

ls -la
aws lambda update-function-code \
    --function-name "clarvoDocumentProcessor" \
    --s3-bucket "aip-c01-bucket" \
    --s3-key "lambda/lambda_function.zip" \
    --query 'LogResult' \
    --region ap-southeast-1 \
    --output text | base64 --decode

