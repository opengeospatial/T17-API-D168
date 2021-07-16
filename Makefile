## Configuration for Makefile.
DOCKER_ID := 13fcbd316920
DOCKER_REPO := 135183637775.dkr.ecr.eu-west-2.amazonaws.com
DOCKER_IMAGE := tb17_apiexperiments_featuresserver_python
DOCKER_VERSION := latest

## Login to AWS via Docker for upload/download of container image
login:
	aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin $(DOCKER_REPO)
login_ogc:
	aws ecr get-login-password --region eu-west-2 --profile ogc | docker login --username AWS --password-stdin $(DOCKER_REPO)
logout:
	docker logout

## Running container
run_docker:
	docker run -p 8080:8080 $(DOCKER_REPO)/$(DOCKER_IMAGE)
## Running catalog building code
build_catalog_records:
	~/.conda/envs/ogcapi/bin/python ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v

build_catalog_stac:
	~/.conda/envs/ogcapi/bin/python ~/ogcapi_testbed17_dataset_d168/build_catalog/create_catalog.py -v --stac


