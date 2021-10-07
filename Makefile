## Configuration for Makefile.
MNAME := $(shell hostname)
# AWS IP num
ifeq ($(MNAME),ip-10-1-2-228)
  PYTHON := ~/.conda/envs/ogcapi/bin/python 
else
  PYTHON := ~/anaconda3/envs/ogcapi/bin/python 
endif

DOCKER_ID := 13fcbd316920
AWS_REPO := 135183637775.dkr.ecr.eu-west-2.amazonaws.com
DOCKER_REPO := arnevogt
DOCKER_IMAGE := tb17_apiexperiments_featureserver_python
DOCKER_VERSION := latest

## Running code to build the catalog
build_catalog_records:
	$(PYTHON) ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v
build_catalog_stac:
	$(PYTHON) ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v --stac


## Login to AWS via Docker for upload/download of container image
login:
	aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin $(AWS_REPO)
login_ogc:
	aws ecr get-login-password --region eu-west-2 --profile ogc | docker login --username AWS --password-stdin $(AWS_REPO)
login_user:
	aws ecr get-login-password --region eu-west-2 --profile user | docker login --username AWS --password-stdin $(AWS_REPO)
logout:
	docker logout

## List container repos
list_local:
	docker container ls
list_aws:
	aws ecr describe-repositories --profile user --region eu-west-2

## Pulling docker container for catalog deployment api server
pull_aws:
	docker pull $(AWS_REPO)/$(DOCKER_IMAGE)
pull_docker:
	docker pull $(DOCKER_REPO)/$(DOCKER_IMAGE)

## Running container for catalog deployment api server
# 8080 HTTP interface 8443 HTTPS interface
run_docker_default:
	docker run --expose 8443 -p 8443:443/tcp -p 8080:8080/tcp -v ~/.aws/credentials:/root/.aws/credentials:ro -v ~/ogcapi_testbed17_dataset_d168/deploy_catalog/backend_configuration.json:/usr/src/app/backend_configuration.json $(DOCKER_REPO)/$(DOCKER_IMAGE)
run_docker_background_default:
	docker run -d --expose 8443 -p 8443:443/tcp -p 8080:8080/tcp -v ~/.aws/credentials:/root/.aws/credentials:ro -v ~/ogcapi_testbed17_dataset_d168/deploy_catalog/backend_configuration.json:/usr/src/app/backend_configuration.json $(DOCKER_REPO)/$(DOCKER_IMAGE)
run_docker_user:
	docker run -p 8080:8080 --env AWS_PROFILE=user -v ~/.aws/credentials:/root/.aws/credentials:ro -v ~/ogcapi_testbed17_dataset_d168/deploy_catalog/backend_configuration.json:/usr/src/app/backend_configuration.json $(DOCKER_REPO)/$(DOCKER_IMAGE)
run_docker_background_user:
	docker run -d -p 8080:8080 --env AWS_PROFILE=user -v ~/.aws/credentials:/root/.aws/credentials:ro -v ~/ogcapi_testbed17_dataset_d168/deploy_catalog/backend_configuration.json:/usr/src/app/backend_configuration.json $(DOCKER_REPO)/$(DOCKER_IMAGE)



