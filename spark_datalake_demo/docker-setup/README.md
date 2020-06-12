# Docker build environment for local_job_runner

## Setup (linux)
This assumes docker is installed and running, for help here see => https://docs.docker.com/install/

Docker compose (https://docs.docker.com/compose/install/) is not required, but this guide assumes it will be used for postgres.  The preferred method of install is to run docker-compose within a docker container, so the install script will create a script to run `docker-compose` as a container.
```text
$ sudo curl -L "https://github.com/docker/compose/releases/download/1.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
$ sudo chmod +x /usr/local/bin/docker-compose
```

Create a directory directory for storing global datalake files, this can go anywhere, but this guides assumes it is a folder called 'data' located under hca-datalake. Note the container will create these if they don't exist.
```text
$ mkdir -p data/mart
$ mkdir -p data/raw
```

Use environment.ini for docker with contents as follows, see scripts/environment.docker.ini in repo:
```text
[db]
url=jdbc:postgresql://postgres:5432/hca_dev
database=hca_dev
user=hca_dev
password=hca_dev
[folders]
datamart=/data/mart
raw=/data/raw
```

## Running jobs
First start database with docker compose, this will spin up a new postgres db and run flyway to create tables:
```text
$ docker-compose up
```

Sample to connect to local postgres db from local machine, outside of docker, like from a database ide:
```text
$ psql -hlocalhost -Uhca_dev -p5432 hca_dev
```

Add sample files to either global datalake folder or to job tests folder.

Then build container or pull existing image from AWS ECR (I put it in the dev account for now, but we can throw it in datalake account too if needed):

**Option 1** -> Build container
```text
$ docker build . -t hca-datalake
```

**Option 2** -> Use existing image (assumes you have an AWS profile created as identity-dev and ecr repo is in us-east-2, adjust accordingly)
```text
$ $(aws ecr get-login --no-include-email --region us-east-2 --profile identity-dev)
$ docker pull 232930948780.dkr.ecr.us-east-2.amazonaws.com/hca-datalake-jhagen:latest
```

Run job per spec in scripts/local_job_runner
```text
$ docker run -it --rm \
    --network hca-datalake_default \ 
    -v $(pwd)/data-mart/etl/etl-jobs/src:/etl-jobs/src \
    -v $(pwd)/data-mart/etl/etl-jobs/scripts/environment.docker.ini:/etl-jobs/scripts/environment.ini \
    -v $(pwd)/data:/data \
    hca-datalake \
    ./local_job_runner fund.fund_composite --schema hdm --datalake global --raw-folder global
```
Notes:
- `-it` run in foreground and show all the logs, exit container when command is finished
- `--rm` do not save container on system, without this containers will accumulate and eat disk space, we are using them statelessly, so it is good habit to use this
- `--network hca-datalake_default` run this container on same network as postgres, this was created automatically with docker compose and allows us to access postgres db from within docker as the service name => `postgres`
- `-v $(pwd)/data-mart/etl/etl-jobs/src:/etl-jobs/src` overlay jobs directory into container, this makes our local code changes overlay what is already in the container so we can test without having to rebuild the image
- `-v $(pwd)/data-mart/etl/etl-jobs/scripts/environment.docker.ini:/etl-jobs/scripts/environment.ini` mount our local environment.ini into the container, required by local_job_runner
- `-v $(pwd)/data:/data` mount our local datalake directory into container under /data, this is where global parquet files will be written and where global raw files would be picked up
- `232930948780.dkr.ecr.us-east-2.amazonaws.com/hca-datalake-jhagen:latest` image name, if you built the image locally, just use whatever you tagged it, in my example above it was called `hca-datalake`
- `./local_job_runner` command we want to run, pass arguments to it same as you would running it as a script, add `--help` to see options

# Postgres
To access postgres from your machine, use localhost for host name and port = 5432 or whatever was set in docker-compose.yml. Within docker network db can be accessed as `postgres`, do not use localhost as it will not work.
