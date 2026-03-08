#!/bin/bash

# Variables
SERVICE_NAME="agoge-react"
PROJECT="ualr-cybersecurity"
IMAGE="gcr.io/${PROJECT}/agoge-react"
REGION="us-central1"


gcloud builds submit . --tag $IMAGE

# Deploy the service initially
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --cpu 4 \
  --memory=4096Mi \
  --platform managed \
  --allow-unauthenticated \
  --service-account="agoge-react-service@${PROJECT}.iam.gserviceaccount.com"
