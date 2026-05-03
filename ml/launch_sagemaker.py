"""
Launch transformer training job on SageMaker using boto3 directly.

1. Packages training code into tar.gz and uploads to S3
2. Uploads dataset to S3
3. Creates a SageMaker training job with a PyTorch container
4. Waits for completion and downloads model artifacts
"""

import os
import sys
import json
import tarfile
import time
import boto3

BUCKET = "astraiosbucket"
PREFIX = "ml/training"
REGION = "us-east-1"
JOB_PREFIX = "astraios-transformer"

PYTORCH_IMAGE = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.1.0-gpu-py310-cu121-ubuntu20.04-sagemaker-v1.6"


def get_role_arn():
    return "arn:aws:iam::125499242423:role/astrax"


def package_source(ml_dir, output_path):
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(os.path.join(ml_dir, "train.py"), arcname="train.py")


def main():
    ml_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(ml_dir, "dataset.csv")
    if not os.path.exists(dataset_path):
        print("ERROR: dataset.csv not found. Run collect_data.py first.")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=REGION)
    sm = boto3.client("sagemaker", region_name=REGION)
    role_arn = get_role_arn()
    print(f"Role: {role_arn}")

    # Upload dataset
    data_key = f"{PREFIX}/data/dataset.csv"
    print(f"Uploading dataset to s3://{BUCKET}/{data_key}...")
    s3.upload_file(dataset_path, BUCKET, data_key)

    # Package and upload source code
    source_tar = os.path.join(ml_dir, "sourcedir.tar.gz")
    package_source(ml_dir, source_tar)
    source_key = f"{PREFIX}/source/sourcedir.tar.gz"
    print(f"Uploading source to s3://{BUCKET}/{source_key}...")
    s3.upload_file(source_tar, BUCKET, source_key)
    os.remove(source_tar)

    job_name = f"{JOB_PREFIX}-{int(time.time())}"
    print(f"Starting training job: {job_name}")

    hyperparameters = {
        "epochs": "60",
        "batch-size": "256",
        "lr": "0.00005",
        "seq-len": "64",
        "d-model": "256",
        "n-heads": "8",
        "n-layers": "4",
        "d-ff": "512",
        "dropout": "0.25",
    }

    sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={
            "TrainingImage": PYTORCH_IMAGE,
            "TrainingInputMode": "File",
        },
        RoleArn=role_arn,
        InputDataConfig=[
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{BUCKET}/{PREFIX}/data/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
            }
        ],
        OutputDataConfig={
            "S3OutputPath": f"s3://{BUCKET}/{PREFIX}/output/",
        },
        ResourceConfig={
            "InstanceType": "ml.g5.xlarge",
            "InstanceCount": 1,
            "VolumeSizeInGB": 30,
        },
        StoppingCondition={
            "MaxRuntimeInSeconds": 7200,
        },
        HyperParameters={
            **hyperparameters,
            "sagemaker_program": "train.py",
            "sagemaker_submit_directory": f"s3://{BUCKET}/{source_key}",
        },
    )

    print("Waiting for training job to complete...")
    while True:
        resp = sm.describe_training_job(TrainingJobName=job_name)
        status = resp["TrainingJobStatus"]
        secondary = resp.get("SecondaryStatus", "")
        print(f"  Status: {status} ({secondary})")

        if status in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(30)

    if status != "Completed":
        print(f"Training job {status}.")
        if resp.get("FailureReason"):
            print(f"Reason: {resp['FailureReason']}")
        sys.exit(1)

    model_s3 = resp["ModelArtifacts"]["S3ModelArtifacts"]
    print(f"Model artifacts: {model_s3}")

    output_dir = os.path.join(ml_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    local_tar = os.path.join(output_dir, "model.tar.gz")

    model_key = model_s3.replace(f"s3://{BUCKET}/", "")
    print(f"Downloading {model_key}...")
    s3.download_file(BUCKET, model_key, local_tar)

    with tarfile.open(local_tar, "r:gz") as tar:
        tar.extractall(output_dir)
    print(f"Model extracted to {output_dir}/")
    print("Done.")


if __name__ == "__main__":
    main()
