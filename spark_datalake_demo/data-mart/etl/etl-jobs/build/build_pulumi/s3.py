import pulumi, json

def fileproc_lifecycle_rules():
    return [{
        "id": "purge-temporary-files",
        "enabled": True,
        "prefix": "/tmp",
        "expiration": {
            "days":1
        },
        "noncurrentVersionExpiration":{
            "days":1
        }
    }]

def datalake_lifecycle_rules(archive_days=90):
    return [{
        "id": "transition-archive-to-glacier",
        "enabled": True,
        "prefix": "/archive",
        "transitions": [{
            "days": archive_days,
            "storage_class": "GLACIER"
        }]
    }]

def bucket_policy(bucket, kms_key_arn):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            # deny if trying to use non-datalake kms key
            "Effect": "Deny",
            "Principal": "*",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket}/*"
            ],
            "Condition": {
                "StringNotLikeIfExists": {
                    "s3:x-amz-server-side-encryption-aws-kms-key-id": kms_key_arn,
                },
            }
            #TODO deny if missing hca:dataclassification tag
            #TODO only process putting things in /raw should be glue_notification lambda
            #TODO only process putting things in /mart & /archive should be glue jobs
        }]
    })

def fileproc_bucket_policy(bucket, kms_key_arn):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Deny",
            "Principal": "*",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket}/*"
            ],
            "Condition": {
                "StringNotLikeIfExists": {
                    "s3:x-amz-server-side-encryption-aws-kms-key-id": kms_key_arn
                }
            }
        },{
            "Effect": "Allow",
            "Principal": { "AWS": "arn:aws:iam::964890379153:root" }, #TODO create iam role for infra to assume
            "Action": [
                "s3:PutObject*"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket}/raw/*"
            ]
        }]
        #TODO deny putobject unless coming from infra account
        #TODO deny getobject from dstprod/ except for lambda
    })

def scripts_bucket_policy(bucket, kms_key_arn):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Deny",
            "Principal": "*",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket}/*"
            ],
            "Condition": {
                "StringNotLikeIfExists": {
                    "s3:x-amz-server-side-encryption-aws-kms-key-id": kms_key_arn
                }
            }
        },{
            "Effect": "Allow",
            "Principal": {
                "Service": "glue.amazonaws.com"
            },
            "Action": [
                "s3:GetObject*"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket}/*"
            ]
        }]
    })