import json
from typing import List

def dataclassification_policy(bucket_name, data_classification:List[str]):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket_name}/*"
            ],
            "Condition": {
                "ForAnyValue:StringEqualsIfExists": {
                    "s3:ExistingObjectTag/hca:dataclassification": data_classification
                }
            }
        }]
    })

def kms_encrypt_policy(kms_arn):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "kms:Encrypt",
                "kms:GenerateDataKey*",
                "kms:DescribeKey"
            ],
            "Resource": kms_arn
        }]
    })

def kms_usage_policy(kms_arn):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:GenerateDataKey*",
                "kms:DescribeKey"
            ],
            "Resource": kms_arn
        },{
            "Effect": "Allow",
            "Action": [
                "kms:List*",
                "kms:Get*",
                "kms:Describe*",
            ],
            "Resource": "*"
        }]
    })

def get_scripts_policy(scripts_bucket):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:List*"
            ],
            "Resource": [
                f"arn:aws:s3:::{scripts_bucket}/*"
            ]
        }]
    })