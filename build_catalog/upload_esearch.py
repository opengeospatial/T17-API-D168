import os
import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection, helpers
# pip install requests-aws4auth
from requests_aws4auth import AWS4Auth
import click
from click_conf import conf
from elasticsearch_loader import load
from elasticsearch_loader.parsers import json
import logging

home = os.path.expanduser("~")
iam_name = 'ogc'
# Elasticsearch
my_region = 'eu-west-2'
my_service = 'es'
my_eshost = 'search-ogc-t17-d168-yhvlgzft2zhuvdssiaejkyq5lq.eu-west-2.es.amazonaws.com'
# S3 bucket
bucket = 'pixalytics-ogc-api'

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
        if folder in file.key:
            print("Uploading {}".format(file.key))
            yield json.load(file.get()['Body'])

def load_s3(ctx, bucket, folder):
    # Access bucket
    session = boto3.session.Session(profile_name=iam_name)
    s3 = session.resource('s3')
    bucket_obj = s3.Bucket(bucket)

    # Load data from S3 bucket to Elasticsearch
    load(s3_iterator(bucket_obj, folder), ctx.obj)

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
    codedir, program = os.path.split(__file__)
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG if opts['verbose'] else logging.INFO)

    if opts['diagnose']:
        # Connect
        es = iam_connect()

        # Check health
        es.cluster.health()

        # Dump info
        print(json.dumps(es.info(), indent=2))

    elif opts['upload']:
        # define options
        ctx.obj = opts
        ctx.obj['index'] = 'stac-index'
        ctx.obj['type'] = 's3'
        ctx.obj['es_conn'] = iam_connect()

        # Upload data to elasticsearch
        load_s3(ctx, bucket, folder="eo4sas-catalog-stac-v0-5")

    else:
        # Query test-index
        es = iam_connect()
        res = es.search(index="stac-index", doc_type="articles", body={"query": {"match": {"content": "20191115"}}})

        print("{} documents found".format(res['hits']['total']))
        for doc in res['hits']['hits']:
                print("{}) {}".format(doc['_id'], doc['_source']['content']))

        # Add an extra field
        # es.create(index="test-index", doc_type="articles", body={"content": "One more fox"})

    logger.info("Processing completed")


if __name__ == "__main__":
    exit(main())
