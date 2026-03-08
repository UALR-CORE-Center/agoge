#!/bin/bash

# Variables

SERVICE_NAME="agoge-api"
REGION="us-central1"
#PROJECT="agoge-test-427119"
#PROJECT="dev-razornet"
#PROJECT="razornet-online"
PROJECT="ualr-cybersecurity"
IMAGE="gcr.io/${PROJECT}/agoge-api"

gcloud builds submit . --tag $IMAGE

# Deploy the service initially
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --cpu 4 \
  --memory=4096Mi \
  --platform managed \
  --allow-unauthenticated \
  --service-account="agoge-service@${PROJECT}.iam.gserviceaccount.com" \
  --min-instances=1
