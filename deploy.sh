#!/bin/bash

#Suggest deploying to us-east-1 due to CE API, and SES
export AWS_DEFAULT_REGION=us-east-1 
#Change the below, an s3 bucket to store lambda code for deploy, and output report
#Must be in same region as lambda (ie AWS_DEFAULT_REGION)
export BUCKET=embark-cost-explorer-reports
#Comma Seperated list of emails to send to
export SES_TO=mzhong@embarkvet.com
export SES_FROM=mzhong@embarkvet.com
export SES_REGION=us-east-1
#Comma Seperated list of Cost Allocation Tags (must be configured in AWS billing prefs)
export COST_TAGS=""
#Do you want partial figures for the current month (set to true if running weekly/daily)
export CURRENT_MONTH=true
#Day of Month, leave as 6 unless you want to capture refunds and final support values, then change to 12
export DAY_MONTH=6
#Number of trailing days to report on
export TRAILING_DAYS=7

mkdir -p bin
cd src
zip -ur ../bin/lambda.zip *.py
cd ..
aws cloudformation package \
   --template-file src/sam.yaml \
   --output-template-file deploy.sam.yaml \
   --s3-bucket $BUCKET \
   --s3-prefix aws-cost-explorer-report-builds
aws cloudformation deploy \
  --template-file deploy.sam.yaml \
  --stack-name aws-cost-explorer-report \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides SESSendFrom=$SES_FROM S3Bucket=$BUCKET \
  SESSendTo=$SES_TO SESRegion=$SES_REGION \
  AccountLabel=Email ListOfCostTags=$COST_TAGS CurrentMonth=$CURRENT_MONTH \
  DayOfMonth=$DAY_MONTH
