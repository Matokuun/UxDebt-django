#!/bin/sh

docker build -t matomaniaco/issue-tracker-images . --no-cache
docker push matomaniaco/issue-tracker-images