#!/bin/bash

export AWS_PROFILE=408897322877_AdministratorAccess

aws lambda invoke \
  --function-name clarvoDocumentProcessor \
  --cli-binary-format raw-in-base64-out \
  --payload file://scripts/test-event.json \
  --region ap-southeast-1 \
  response.json