import os
import sys
import subprocess
from argparse import Namespace, ArgumentParser
import glob
import boto3, json
from elasticsearch import Elasticsearch, RequestsHttpConnection, helpers
# pip install requests-aws4auth
from requests_aws4auth import AWS4Auth

import logging

my_region = 'eu-west-2'
my_service = 'es'
my_eshost = 'search-ogc-t17-d168-yhvlgzft2zhuvdssiaejkyq5lq.eu-west-2.es.amazonaws.com'


def main(args: Namespace = None) -> int:
    if args is None:
        parser = ArgumentParser(
            description="Uploads data to Elasticsearch",
            epilog="Should be run in the 'ogcapi' environment",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            help="Add extra information to logs.",
            action="store_true",
            default=False,
        )

    # define arguments
    args = parser.parse_args()

    # Start logging
    codedir, program = os.path.split(__file__)
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG if "verbose" in args and args.verbose else logging.INFO)

    # Upload data to elasticsearch
    # Get sessaion credentials for profile ogc
    session = boto3.Session(region_name=my_region,
                            profile_name='ogc')
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

    es = Elasticsearch(
        hosts=[{'host': my_eshost, 'port': 443}],
        http_auth=aws_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

    # Check health
    es.cluster.health()

    # Dump info
    print(json.dumps(es.info(), indent=2))

    # Upload csv file
    #ES_index = filename.split(".")[0]
    #with open(filename) as f:
    #        reader = csv.DictReader(f)
    #        helpers.bulk(es, reader, index=ES_index, doc_type='my-type')

    # Query test-index
    res = es.search(index="test-index", doc_type="articles", body={"query": {"match": {"content": "fox"}}})

    print("{} documents found".format(res['hits']['total']))
    for doc in res['hits']['hits']:
            print("{}) {}".format(doc['_id'], doc['_source']['content']))

    # Add an extra field
    # es.create(index="test-index", doc_type="articles", body={"content": "One more fox"})

    logger.info("Processing completed")


if __name__ == "__main__":
    exit(main())
