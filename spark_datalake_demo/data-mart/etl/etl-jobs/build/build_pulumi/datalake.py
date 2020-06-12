import pulumi
from pulumi_aws import s3, kms, iam, get_caller_identity, glue, cloudwatch
from s3 import datalake_lifecycle_rules, fileproc_lifecycle_rules, bucket_policy, fileproc_bucket_policy, scripts_bucket_policy
from kms import key_policy
from iam import dataclassification_policy, kms_usage_policy, kms_encrypt_policy, get_scripts_policy
import json
from typing import Dict, Callable

class DatalakeInfra(pulumi.ComponentResource):
    datalake_bucket: s3.Bucket
    fileproc_bucket: s3.Bucket
    scripts_bucket: s3.Bucket
    kms_key: kms.Key
    glue_security_config: glue.SecurityConfiguration

    # iam policies
    policy_kms_full_usage: iam.Policy
    policy_kms_encrypt_only: iam.Policy
    policy_get_object_pii: iam.Policy
    policy_get_object_confidential: iam.Policy
    policy_get_object_nonsensitive: iam.Policy
    policy_get_scripts: iam.Policy
    policy_glue_service: iam.Policy

    raw_location: pulumi.Output[str]
    mart_location: pulumi.Output[str]
    delta_location: pulumi.Output[str]
    archive_location: pulumi.Output[str]

    def __init__(self, name, 
            tags:Dict[str,str]=None, 
            opts:pulumi.ResourceOptions=None):
        super().__init__('hca:DatalakeInfra', name, None, opts)

        aws_region = pulumi.Config('aws').get('region')

        self.tags = tags if tags is None else {}
      
        identity = get_caller_identity()
        self.kms_key = kms.Key(f"{name}-kms-key",
            description="kms key for encryption of datalake",
            policy=key_policy(identity.account_id, aws_region),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self))

        alias = kms.Alias(f"{name}-kms-key-alias",
            target_key_id=self.kms_key.id,
            name=f"alias/hca/{name}",
            opts=pulumi.ResourceOptions(parent=self, delete_before_replace=True))

        # create datalake bucket
        self.datalake_bucket = s3.Bucket(f"{name}-bucket",
            lifecycle_rules=datalake_lifecycle_rules(),
            server_side_encryption_configuration={
                'rule': {
                    'applyServerSideEncryptionByDefault': {
                        'kmsMasterKeyId': self.kms_key.arn,
                        'sseAlgorithm': 'aws:kms'
                    }
                }
            },
            versioning={ 'enabled': True },
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPolicy(f"{name}-bucket-policy",
            bucket=self.datalake_bucket,
            policy=pulumi.Output.all(self.datalake_bucket.bucket, self.kms_key.arn).apply(lambda p: bucket_policy(p[0],p[1])),
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPublicAccessBlock(f"{name}-access-block",
            bucket=self.datalake_bucket,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=pulumi.ResourceOptions(parent=self))

        # define folder paths for datalake bucket
        self.raw_location = self.datalake_bucket.bucket.apply(lambda b: f"s3://{b}/raw")
        self.mart_location = self.datalake_bucket.bucket.apply(lambda b: f"s3://{b}/mart")
        self.archive_location = self.datalake_bucket.bucket.apply(lambda b: f"s3://{b}/archive")
        self.delta_location = self.datalake_bucket.bucket.apply(lambda b: f"s3://{b}/delta")
        
        # create fileproc bucket
        self.fileproc_bucket = s3.Bucket(f"{name}-fileproc-bucket",
            lifecycle_rules=fileproc_lifecycle_rules(),
            server_side_encryption_configuration={
                'rule': {
                    'applyServerSideEncryptionByDefault': {
                        'kmsMasterKeyId': self.kms_key.arn,
                        'sseAlgorithm': 'aws:kms'
                    }
                }
            },
            versioning={ 'enabled': True },
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPolicy(f"{name}-fileproc-bucket-policy",
            bucket=self.fileproc_bucket,
            policy=pulumi.Output.all(self.fileproc_bucket.bucket, self.kms_key.arn).apply(lambda p: fileproc_bucket_policy(p[0],p[1])),
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPublicAccessBlock(f"{name}-fileproc-access-block",
            bucket=self.fileproc_bucket,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=False,
            opts=pulumi.ResourceOptions(parent=self))

        # create scripts bucket
        self.scripts_bucket = s3.Bucket(f"{name}-script-bucket",
            server_side_encryption_configuration={
                'rule': {
                    'applyServerSideEncryptionByDefault': {
                        'kmsMasterKeyId': self.kms_key.arn,
                        'sseAlgorithm': 'aws:kms'
                    }
                }
            },
            versioning={ 'enabled': True },
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPolicy(f"{name}-script-bucket-policy",
            bucket=self.scripts_bucket,
            policy=pulumi.Output.all(self.scripts_bucket.bucket, self.kms_key.arn).apply(lambda p: scripts_bucket_policy(p[0],p[1])),
            opts=pulumi.ResourceOptions(parent=self))

        s3.BucketPublicAccessBlock(f"{name}-script-access-block",
            bucket=self.scripts_bucket,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=False,
            opts=pulumi.ResourceOptions(parent=self))
        
        # create dataclassification policies for getobject
        dataclassifications = ['pii', 'confidential', 'nonsensitive']

        self.policy_get_object_pii = iam.Policy(f"{name}-pii-policy",
            description="allow get access to pii data",
            policy=self.datalake_bucket.id.apply(lambda b: dataclassification_policy(b, dataclassifications)),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))

        self.policy_get_object_confidential = iam.Policy(f"{name}-confidential-policy",
            description="allow get access to confidential data",
            policy=self.datalake_bucket.id.apply(lambda b: dataclassification_policy(b, dataclassifications[1:])),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))

        self.policy_get_object_nonsensitive = iam.Policy(f"{name}-nonsensitive-policy",
            description="allow get access to nonsensitive data",
            policy=self.datalake_bucket.id.apply(lambda b: dataclassification_policy(b, dataclassifications[2:])),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))

        # create kms policies
        self.policy_kms_full_usage = iam.Policy(f"{name}-iam-key-full-usage",
            description="allow encrypt/decrypt with datalake kms key",
            policy=self.kms_key.arn.apply(kms_usage_policy),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))

        self.policy_kms_encrypt_only = iam.Policy(f"{name}-iam-key-encrypt-only",
            description="allow encrypt only with datalake kms key",
            policy=self.kms_key.arn.apply(kms_encrypt_policy),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))

        # create policy for getting scripts
        self.policy_get_scripts = iam.Policy(f"{name}-get-scripts",
            description="allow get access glue scripts bucket",
            policy=self.scripts_bucket.bucket.apply(get_scripts_policy),
            path='/',
            opts=pulumi.ResourceOptions(parent=self))
        
        # get glue service policy (create custom one later)
        self.policy_glue_service = iam.Policy.get(f"{name}-glue-service", 'arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole', opts=pulumi.ResourceOptions(parent=self))

        # create glue security config
        # use specific name as any changes will trigger replacement of resource
        self.glue_security_config = glue.SecurityConfiguration(f"{name}-security-config",
            name=name,
            encryption_configuration={
                'cloudwatchEncryption': {
                    'cloudwatchEncryptionMode': 'SSE-KMS',
                    'kms_key_arn': self.kms_key.arn
                },
                's3Encryption': {
                    's3EncryptionMode': 'SSE-KMS',
                    'kms_key_arn': self.kms_key.arn
                },
                'jobBookmarksEncryption': {
                    'jobBookmarksEncryptionMode': 'DISABLED'
                }
            },
            opts=pulumi.ResourceOptions(parent=self))
    
    def add_fileproc_notifications(self, name, lambda_function_notifications=None):
        if lambda_function_notifications is None:
            lambda_function_notifications = []

        s3.BucketNotification('fileproc-bucket-notification',
            bucket=self.fileproc_bucket,
            lambda_functions=lambda_function_notifications)

    def add_scripts_notifications(self, name, lambda_function_notifications=None):
        if lambda_function_notifications is None:
            lambda_function_notifications = []

        s3.BucketNotification('script-bucket-notification',
            bucket=self.scripts_bucket,
            lambda_functions=lambda_function_notifications)
