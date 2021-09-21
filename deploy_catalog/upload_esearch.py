import os
import sys
import boto3
# pip install elasticsearch==7.13.4
# More recent versions of the elasticsearch python library do not support AWS, see https://www.theregister.com/2021/08/09/elasticsearch_python_client_change/
from elasticsearch import Elasticsearch, RequestsHttpConnection, helpers
# pip install requests-aws4auth
from requests_aws4auth import AWS4Auth
import click
from click_conf import conf
from elasticsearch_loader import load
from elasticsearch_loader.parsers import json
import yaml
import logging

home = os.path.expanduser("~")
codedir, program = os.path.split(__file__)
CONFIGURATION_FILE_PATH = os.path.join(codedir, "es_upload_conf.yaml")

if not os.path.exists(CONFIGURATION_FILE_PATH):
    print("Configuration file is missing")

try:
    with open(CONFIGURATION_FILE_PATH, "r") as config_file:
        config = yaml.safe_load(config_file)
        # AWS IAM user stored in ~/.aws/credentials
        iam_name = config["iam_name"]
        # Elasticsearch
        my_region = config["my_region"]
        my_service = config["my_service"]
        my_eshost = config["my_eshost"]
        catalog = config["catalog"]
        splits = catalog.split("-")
        if splits[3] == "nc":
            index = "{}-index-nc".format(splits[2])
        else:
            index = "{}-index".format(splits[2])
        print("Uploading to {}".format(index))
        # S3 bucket
        bucket = config["bucket"]

        print("Configuration was loaded from '{}'.".format(CONFIGURATION_FILE_PATH))

except Exception:
    print("Unable to load default configuration from '{}'.".format(CONFIGURATION_FILE_PATH))
    sys.exit(1)


def iam_connect():
    # Get session credentials for profile ogc
    session = boto3.Session(region_name=my_region,
                            profile_name=iam_name)
    credentials = session.get_credentials()
    credentials = credentials.get_frozen_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    token = credentials.token

    aws_auth = AWS4Auth(
        access_key,
        secret_key,
        my_region,
        my_service,
        session_token=token
    )

    print("Logging in as {}".format(iam_name))
    es = Elasticsearch(
        hosts=[{'host': my_eshost, 'port': 443}],
        http_auth=aws_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return es

def master_connect():
    # Load master credentials
    with open(os.path.join(home, 'esearch.txt'), 'r') as f1:
        first_line = f1.readline().rstrip("\n")
        credentials = first_line.split(",")

    print("Logging in as {}".format(credentials[0]))
    es = Elasticsearch(
        hosts=[{'host': my_eshost, 'port': 443}],
        http_auth=(credentials[0], credentials[1]),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return es

def s3_iterator(bucket, folder):
    for file in bucket.objects.all():
        if folder in file.key and "catalog.json" not in file.key:
            content = json.load(file.get()['Body'])
            print("Uploading {} from {}".format(content,file.key))
            yield content

def load_s3(ctx, index, bucket, folder):
    # Access bucket
    session = boto3.session.Session(profile_name=iam_name)
    s3 = session.resource('s3')
    bucket_obj = s3.Bucket(bucket)

    # Creat index and upload mapping to index file
    mapfile = open(os.path.join(codedir, "index_settings_file.json"), 'rb')
    response = ctx.obj['es_conn'].indices.create(index=index, body=json.load(mapfile))
    mapfile.close()
    if 'acknowledged' in response:
        if response['acknowledged'] == True:
            print("Index mapping success for: {}".format(response['index']))
    # catch API error response
    elif 'error' in response:
        print("ERROR:", response['error']['root_cause'])
        print("TYPE:", response['error']['type'])
        return

    # Load data from S3 bucket to Elasticsearch
    #load(s3_iterator(bucket_obj, folder), ctx.obj)
    count = 0
    for file in bucket_obj.objects.all():
        #print("File: {}".format(file.key))
        if folder in file.key and "catalog.json" not in file.key:
            content = json.load(file.get()['Body'])
            response = ctx.obj['es_conn'].index(index=index, id=count, body=content)
            print("Uploading {} from {}: {}".format(content, file.key, response['result']))

            count += 1
    if count == 0:
        print("No files matched to upload")
    else:
        print("Completed uploading")


@click.group(invoke_without_command=True, context_settings={"help_option_names": ['-h', '--help']})
@conf(default='esl.yml')
@click.option('--bulk-size', default=500, help='How many docs to collect before writing to Elasticsearch (default 500)')
@click.option('--id-field', help='Specify field name that be used as document id')
@click.option('--keys', type=str, help='Comma separated keys to pick from each document', default='', callback=lambda c, p, v: [x for x in v.split(',') if x])
@click.option('--progress', default=False, is_flag=True, help='Enable progress bar - NOTICE: in order to show progress the entire input should be collected and can consume more memory than without progress bar')
@click.option('--update', default=False, is_flag=True, help='Merge and update existing doc instead of overwrite')
@click.option('--with-retry', default=False, is_flag=True, help='Retry if ES bulk insertion failed')
@click.option('--diagnose', default=False, is_flag=True, help='Run diagnosis as master user')
@click.option('--upload', default=False, is_flag=True, help='Upload as master user')
@click.option('--verbose', default=False, is_flag=True, help='Add extra information to logs')
@click.pass_context
def main(ctx, **opts):

    # Start logging
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG if opts['verbose'] else logging.INFO)

    if opts['diagnose']:
        # Connect
        es = iam_connect()

        # Check health
        print("Health: ")
        es.cluster.health()

        print("\nInfo: ")
        # Dump info
        print(json.dumps(es.info(), indent=2))

        # List indices
        print("\nAvailable indices: {}".format(es.indices.get_alias("*")))

    elif opts['upload']:
        # define options
        ctx.obj = opts
        ctx.obj['index'] = index
        ctx.obj['type'] = 'json'
        ctx.obj['es_conn'] = iam_connect()

        # Delete index before uploading
        ctx.obj['es_conn'].indices.delete(index=index, ignore=[400, 404])

        # Upload data to elasticsearch
        load_s3(ctx, index, bucket, folder=catalog)


    else:
        # Query test-index
        es = iam_connect()

        # returns dict object of the index _mapping schema
        raw_data = es.indices.get_mapping(index)
        print("\nget_mapping response type: {}".format(type(raw_data)))

        # returns dict_keys() obj in Python 3
        mapping_keys = raw_data[index]["mappings"].keys()
        print("mapping keys: {}".format(mapping_keys))

        # interrogate the schema by accessing index's _doc type attr'
        schema = raw_data[index]["mappings"]["properties"]
        print (json.dumps(schema, indent=4))
        print ("{} fields in mapping".format(len(schema)))
        print("all fields: {}".format(list(schema.keys())))

        # Get first document in index
        result = es.get(index=index, id=1)
        print("First id for {}: {}".format(index,result))

        body = {'query': {'bool': {'must': [{'match': {'type': 'Feature'}}]}}}
        res = es.search(index=index, body=body)

        print("For {} found {}".format(index, res['hits']['total']))
        for doc in res['hits']['hits']:
            print("{} {}".format(doc['_id'], doc['_source']['id']))

    logger.info("Processing completed")


if __name__ == "__main__":
    exit(main())
