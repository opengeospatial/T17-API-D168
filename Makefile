## Configuration for Makefile.
MNAME := $(shell hostname)
# AWS IP num
ifeq ($(MNAME),ip-10-1-2-228)
  PYTHON := ~/.conda/envs/ogcapi/bin/python 
else
  PYTHON := ~/anaconda3/envs/ogcapi/bin/python 
endif

DOCKER_ID := 13fcbd316920
#DOCKER_REPO := 135183637775.dkr.ecr.eu-west-2.amazonaws.com
DOCKER_REPO := arnevogt
DOCKER_IMAGE := tb17_apiexperiments_featureserver_python
DOCKER_VERSION := latest

## Login to AWS via Docker for upload/download of container image
login:
	aws ecr get-login-password --region eu-west-2 --profile ogc | docker login --username AWS --password-stdin $(DOCKER_REPO)
login_arne:
	aws ecr get-login-password --region eu-west-2 --profile user | docker login --username AWS --password-stdin $(DOCKER_REPO)
logout:
	docker logout

## List container repos
list:
	aws ecr describe-repositories --profile user --region eu-west-2

## Pulling docker container
pull_docker:
	docker pull $(DOCKER_REPO)

## Running container
run_docker:
	docker run -p 8080:8080 --env AWS_PROFILE=user -v ~/.aws/credentials:/root/.aws/credentials:ro -v ~/sajh/pixinternal/ogcapi_testbed17_dataset_d168/deploy_catalog/backend_configuration.json:/usr/src/app/backend_configuration.json $(DOCKER_REPO)/$(DOCKER_IMAGE)

## Running catalog building code
build_catalog_records:
	$(PYTHON) ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v

build_catalog_stac:
	$(PYTHON) ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v --stac


