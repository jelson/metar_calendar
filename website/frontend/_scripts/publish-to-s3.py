#!/usr/bin/env python3

import datetime
import boto3
import json
import os
import subprocess
import sys
import tempfile
import time

AWS_PROFILE = 'jelson-personal'
HTACCESS_FUNC_NAME = 'AvMapperHTAccess'
BUCKET = 'avmapper.com'
DISTRIBUTION_ID = 'E39PVZW9UJ3RUQ'

def get_cloudfront_function(htaccess_path):
    with open(os.path.join(os.path.dirname(__file__), "cloudfront-function-template.js")) as ifh:
        template = ifh.read()

    redirects = {}

    for line in open(htaccess_path):
        parts = line.split()
        if len(parts) != 4 or parts[0] != 'Redirect':
            continue

        redirects[parts[2]] = parts[3]

    out = template.replace('@REDIRECTS@', json.dumps(redirects, indent=3))
    os.remove(htaccess_path)
    return out.encode('utf-8')

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f'Emitting to {tmpdir}')
        date = str(datetime.datetime.now().replace(microsecond=0))

        subprocess.check_call([
            "bundle", "exec", "jekyll", "build", "-d", tmpdir,
        ], cwd=os.path.join(os.path.dirname(__file__), ".."))

        os.environ['AWS_PROFILE'] = AWS_PROFILE

        # upload the htaccess function and delete htaccess
        print("Generating new htaccess-ish cloudfront function")
        cloudfront_function = get_cloudfront_function(os.path.join(tmpdir, ".htaccess"))

        print("Syncing to s3")
        subprocess.check_call([
            "aws", "s3", "sync", "--delete", tmpdir, f"s3://{BUCKET}",
        ])

        session = boto3.Session(profile_name=AWS_PROFILE)
        client = session.client('cloudfront')

        oldfunc = client.describe_function(Name=HTACCESS_FUNC_NAME)
        oldfunc_etag = oldfunc['ResponseMetadata']['HTTPHeaders']['etag']
        rv = client.update_function(
            Name=HTACCESS_FUNC_NAME,
            FunctionConfig={
                'Comment': f'AvMapper HTAccess function {date}',
                'Runtime': 'cloudfront-js-2.0',
            },
            FunctionCode=cloudfront_function,
            IfMatch=oldfunc_etag,
        )
        newfunc_etag = rv['ResponseMetadata']['HTTPHeaders']['ettag']
        client.publish_function(
            Name=HTACCESS_FUNC_NAME,
            IfMatch=newfunc_etag,
        )

        print("Generating invalidation to make site live")
        rv = client.create_invalidation(
            DistributionId=DISTRIBUTION_ID,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': [
                        '/*'
                    ],
                },
                'CallerReference': date,
            }
        )
        print(rv)

main()
