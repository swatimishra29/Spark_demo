import pulumi
from pulumi_aws import iam, glue
from datalake import DatalakeInfra
from functions import glue_notification, scripts_archive
from distribution import EtlJobDist
from etljob import GlueEtlJob, etljob_policy
from jobworkflow import JobWorkflow, WorkflowDefinition
from typing import Dict, List
from datetime import datetime
import os, sys
sys.path.insert(0, "../../src")
import pkgutil, jobs as jobsdir
import json
import glob

project = pulumi.get_project()
env = pulumi.get_stack()
aws_region = pulumi.Config('aws').get('region')

# tag everything with pulumi stack + project
tags = {
    'hca:pulumi_stack': pulumi.get_stack(),
    'hca:pulumi_project': pulumi.get_project()
}

# not supported yet, thought would be to revert to prior version
#existing_dist = pulumi.Config().get('existing_dist')

# relative paths for folders used in distribution
dist_dir = os.path.abspath('../dist')
workflow_dir = os.path.abspath('../../src/metadata/workflows')

# TODO figure out better sanity check for aws -> pulumi mapping

infra = DatalakeInfra(f"datalake-{env}", tags=tags)

# create fileproc -> glue trigger function
glue_notification_dist_dir = os.path.join(dist_dir, 'lambda-glue-notification')
glue_notification = glue_notification.GlueNotificationLambda("glue-notification", 
    datalake_bucket=infra.datalake_bucket,
    datalake_raw_path='raw/', #TODO centralize these paths somewhere
    fileproc_bucket=infra.fileproc_bucket,
    managed_policy_arns=[
        infra.policy_kms_full_usage.arn,
        'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    ],
    package_dir=glue_notification_dist_dir,
    tags=tags)

infra.add_fileproc_notifications("fileproc-notification", [
    {
        'events': ['s3:ObjectCreated:*'],
        'lambda_function_arn': glue_notification.function.arn
    }
])

# create scripts bucket archiving function
script_archive = scripts_archive.ScriptArchiveLambda('script-archive',
    scripts_bucket=infra.scripts_bucket,
    managed_policy_arns=[
        infra.policy_kms_full_usage,
        'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    ],
    tags=tags)

infra.add_scripts_notifications("scripts-notification", [
    {
        'events': ['s3:ObjectCreated:*'],
        'lambda_function_arn': script_archive.function.arn,
        'filterPrefix': 'working/'
    }
])

# prepare distribution and copy to s3 bucket
SCRIPTS_VERSION = os.environ.get('SCRIPTS_VERSION', f"local-{datetime.now().strftime('%Y%m%d%H%M%S')}")

# pulumi uploads to {scripts_bucket}/working
etldist = EtlJobDist('distribution', 
    scripts_bucket=infra.scripts_bucket,
    scripts_version=SCRIPTS_VERSION,
    datalake_bucket=infra.datalake_bucket,
    dist_dir=dist_dir,
    tags=tags)

# get job dependencies for building iam policies
with open(os.path.join(glue_notification_dist_dir,'job_dependencies.json')) as f:
    job_dependencies = json.load(f)

# create iam policy for glue etl jobs
etl_job_policy = iam.Policy('etl-job-policy',
    description=f"",
    path='/glue/',
    policy=pulumi.Output.all(infra.datalake_bucket.arn, infra.scripts_bucket.arn).apply(lambda buckets: etljob_policy(buckets[0], buckets[1])))

# create etljobs, map by job name
gluejobs:Dict[str,GlueEtlJob] = {}
for importer, modname, ispkg in pkgutil.walk_packages(path=jobsdir.__path__, prefix='jobs.'):
    if not ispkg:
        jobname = '.'.join(modname.split('.')[1:-1])
        
        job_dependency = job_dependencies[jobname] if jobname in job_dependencies else None
        if not job_dependency:
            raise Exception(f"job dependency not found for job => {jobname} from catalog => {job_dependencies.keys()}")

        gluejobs[jobname] = GlueEtlJob(jobname, 
            iam_policies=[
                infra.policy_kms_full_usage.arn,
                infra.policy_glue_service.arn,
                etl_job_policy.arn
            ],
            data_classification=job_dependency['data_sensitivity'],
            target_table=job_dependency['target_table'],
            security_config=infra.glue_security_config,
            script_location=etldist.get_prefixed_s3_uri('glue_job_runner.py'),
            job_args={
                '--hca_job_name': jobname,
                '--raw_location': infra.raw_location,
                '--datamart_location': infra.mart_location,
                '--archive_location': infra.archive_location,
                '--delta_location': infra.delta_location,
                '--aws_region': aws_region,
                '--extra-py-files': etldist.get_extra_py_files(),
                '--enable-metrics': True
            },
            job_db_connections=['Postgres'], #TODO
            job_name_prefix='etl',
            tags=tags)

# create glue jobs for glue_sync_table.py script
sync_table_policy = iam.Policy('sync-table-policy',
    description="policy for script glue_sync_table to allow write to mart folder in datalake",
    path='/glue/',
    policy=pulumi.Output.all(infra.datalake_bucket.arn, infra.scripts_bucket.arn).apply(lambda b: json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            # allow spark to write dumb _$folder$ files
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": f"{b[0]}/*_$folder$"
        },{
            # allow write/delete to mart folder, note this is kind of dangerous...
            "Effect": "Allow",
            "Action": [
                "s3:GetObject*",
                "s3:PutObject*",
                "s3:DeleteObject*"
            ],
            "Resource": f"{b[0]}/mart/*"
        },{
            # allow list whole bucket
            "Effect": "Allow",
            "Action": [
                "s3:GetBucketLocation",
                "s3:GetObjectTagging",
                "s3:ListBucket*",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload",
            ],
            "Resource": [
                b[0],
                b[0]+'/*',
            ]
        },{
            # allow get glue connection (postgres)
            "Effect": "Allow",
            "Action": "glue:GetConnection",
            "Resource": "*"
        },{
            # allow encrypt cloudwatch logs with kms key
            "Effect": "Allow",
            "Action": [
                "logs:AssociateKmsKey"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:/aws-glue/*"
        },{
            # allow get all from scripts bucket
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": [
                b[1],
                b[1] + '/*'
            ]
        }]
    })))

gluejobs['glue_sync_table'] = GlueEtlJob('glue_sync_table',
    iam_policies=[
        infra.policy_kms_full_usage,
        infra.policy_glue_service.arn,
        sync_table_policy.arn
    ],
    script_location=etldist.get_prefixed_s3_uri('glue_sync_table.py'),
    job_args={
        '--table_names': 'hdm.some_table,hdm.some_other_table',
        '--aws_region': aws_region,
        '--datamart_location': infra.mart_location,
        '--write_mode': 'error', #error or overwrite, see spark docs for values of df.write.mode({write_mode})
        '--extra-py-files': etldist.get_extra_py_files(),
        '--enable-metrics': True
    },
    security_config=infra.glue_security_config,
    job_db_connections=['Postgres'], #TODO
    job_name_prefix='sync',
    tags=tags)

# prepare map of project + set[target table]
table_catalog:Dict[str,set] = {}
for _, modname, ispkg in pkgutil.walk_packages(path=jobsdir.__path__, prefix='jobs.'):
    if not ispkg:
        modulename = modname.split('.')[1]
        jobname = '.'.join(modname.split('.')[1:-1])

        job_dependency = job_dependencies[jobname] if jobname in job_dependencies else None
        if not job_dependency:
            raise Exception(f"job dependency not found for job => {jobname} from catalog => {job_dependencies.keys()}")

        table_name = job_dependency['target_table']
        if modulename in table_catalog:
            table_catalog[modulename].add(table_name)
        else:
            table_catalog[modulename] = set([table_name])

# create iam role for crawlers to assume
crawler_role = iam.Role('crawler-role',
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "glue.amazonaws.com"
            }
        }]
    }),
    description="datalake mart crawler",
    force_detach_policies=True,
    path='/glue/',
    name_prefix=f"{project}-{env}-mart-crawler")

# attach policies to crawler role
iam.RolePolicyAttachment('crawler-kms-policy', role=crawler_role, policy_arn=infra.policy_kms_full_usage.arn)
iam.RolePolicyAttachment('crawler-glue-service-policy', role=crawler_role, policy_arn=infra.policy_glue_service.arn)
iam.RolePolicy('crawler-read-mart-policy', 
    role=crawler_role, 
    policy=infra.mart_location.apply(lambda p: json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{p[5:]}/*", #strip s3:// prefix
        },{
            "Effect": "Allow",
            "Action": "logs:AssociateKmsKey",
            "Resource": "*"
        }]
    }))
)

# create crawler to bring mart parquet files into glue catalog
for project in table_catalog:
    glue_db = glue.CatalogDatabase(f"{project}-db",
        name=project,
        description=f"datalake db => {project}")

    glue_crawler = glue.Crawler(f"{project}-crawler",
        description=f"crawler for mart files project => {project}",
        database_name=glue_db.name,
        role=crawler_role.arn,
        s3_targets=infra.mart_location.apply(lambda p, project=project: [{'path': os.path.join(p,f'{table}/')} for table in table_catalog[project]]),
        security_configuration=infra.glue_security_config.name,
        schedule="cron(0 12 * * ? *)", # run daily at 7am
        schema_change_policy={
            'deleteBehavior': 'DEPRECATE_IN_DATABASE',
            'updateBehavior': 'UPDATE_IN_DATABASE'
        })

# create glue workflows and triggers
print(f'reading workflow definitions from directory => {workflow_dir}')
for filepath in glob.glob(workflow_dir + '/*.yaml'):
    wf_name = os.path.splitext(os.path.basename(filepath))[0]

    # read workflow definition from file
    wf_map = WorkflowDefinition(filepath)

    # create workflow using file name as name,
    # pass map of glue jobs as it holds actual job names
    wf = JobWorkflow(wf_name,
        wf_definition=wf_map,
        glue_jobs_map=gluejobs)



pulumi.export('datalake_bucket', infra.datalake_bucket.bucket)
pulumi.export('fileproc_bucket', infra.fileproc_bucket.bucket)
pulumi.export('scripts_bucket', infra.scripts_bucket.bucket)
pulumi.export('kms_key', infra.kms_key.arn)
pulumi.export('glue_security_config', infra.glue_security_config.name)

pulumi.export('policy_kms_full_usage', infra.policy_kms_full_usage.arn)
pulumi.export('policy_kms_encrypt_only', infra.policy_kms_encrypt_only.arn)
pulumi.export('policy_get_object_pii', infra.policy_get_object_pii.arn)
pulumi.export('policy_get_object_confidential', infra.policy_get_object_confidential.arn)
pulumi.export('policy_get_object_nonsensitive', infra.policy_get_object_nonsensitive.arn)
pulumi.export('policy_get_scripts', infra.policy_get_scripts.arn)
pulumi.export('policy_glue_service', infra.policy_glue_service.arn)

pulumi.export('raw_location', infra.raw_location)
pulumi.export('mart_location', infra.mart_location)
pulumi.export('archive_location', infra.archive_location)
pulumi.export('delta_location', infra.delta_location)