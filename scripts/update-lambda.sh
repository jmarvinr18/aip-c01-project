#!/bin/bash

function=$1

if [[ -z "$function" ]]; then
    echo "########################################################"
    echo "## Please provide the function name as an argument.   ##"
    echo "########################################################"
    exit 1
fi

zip -j lambda/$function.zip lambda/$function/lambda_function.py

export AWS_PROFILE=408897322877_AdministratorAccess
aws s3 cp lambda/$function.zip s3://aip-c01-bucket/lambda/$function/

aws s3 ls s3://aip-c01-bucket/lambda/

echo "##################################################################"
echo "## Checking Lambda function: $function                  "
echo "##################################################################"
aws s3 ls s3://aip-c01-bucket/lambda/$function/

aws lambda update-function-code \
    --function-name "$function" \
    --s3-bucket "aip-c01-bucket" \
    --s3-key "lambda/$function/lambda_function.zip" \
    --query 'LogResult' \
    --region ap-southeast-1 \
    --output text | base64 --decode

