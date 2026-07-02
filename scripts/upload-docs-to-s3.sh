#!/bin/bash

export AWS_PROFILE=408897322877_AdministratorAccess

aws s3 cp "/Users/rouvinramoda/Documents/ai-projects/aip-c01-project/documents/Golden Time SOW (signed) (1).pdf" \
    s3://aip-c01-bucket/raw/

# aws cloudwatch get-metric-statistics --namespace AWS/Events \
#   --metric-name TriggeredRules --dimensions Name=RuleName,Value=clarvo-kb-sync \
#   --start-time echo $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
#   --end-time echo $(date -u +%Y-%m-%dT%H:%M:%S) --period 300 --statistics Sum --region ap-southeast-1

# # aws events describe-rule --name s3_to_sns --region ap-southeast-1 --query 'EventPattern'
# aws events describe-rule --name clarvo-kb-sync --region ap-southeast-1 --query 'EventPattern'

# aws lambda add-permission --function-name clarvoKBSync \
#   --statement-id eventbridge-clarvo-kb-sync \
#   --action lambda:InvokeFunction \
#   --principal events.amazonaws.com \
#   --source-arn arn:aws:events:ap-southeast-1:408897322877:rule/clarvo-kb-sync \
#   --region ap-southeast-1
# aws lambda get-policy --function-name clarvoKBSync --region ap-southeast-1
