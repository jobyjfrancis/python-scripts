# Usage
# aws-vault exec <account> -- python3 generate_dms_cf_template.py --db <cluster>-<stack>-<env> --bucket <s3-bucket> --region <aws-region>

import boto3
import json
import argparse
import os

parser = argparse.ArgumentParser(description="Generate Cloudformation template for DMS")
parser.add_argument('--db', required=True, help='environment, cluster-stack-env')
parser.add_argument('--bucket', required=True, help='S3 bucket to store the DMS CF templates')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

source_db = args.db
s3_bucket = args.bucket
aws_region = args.region

target_db = f"{args.db}-encrypted"

def generate_dms_template():

    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "DMS Homogeneous Data Migration Setup",
        "Parameters": {
            "DBPassword": {
                "Type": "String",
                "NoEcho": True,
                "Description": "Database password"
            }
        },
        "Resources": {
            "SourceSecret": {
                "Type": "AWS::SecretsManager::Secret",
                "Properties": {
                    "Name": f"{source_db}-db-secret",
                    "SecretString": {
                        "Fn::Sub": [
                            '{ "username": "cosmos", "password": "${DBPassword}", "engine": "mysql", "host": "${source_db_endpoint}", "port": 3306, "dbname": "${source_db}" }',
                            {
                                "SOURCE_DB_ENDPOINT": source_db_endpoint,
                                "SOURCE_DB": source_db
                            }
                        ]
                    }
                }
            },
            "TargetSecret": {
                "Type": "AWS::SecretsManager::Secret",
                "Properties": {
                    "Name": f"{target_db}-db-secret",
                    "SecretString": {
                        "Fn::Sub": [
                            '{ "username": "cosmos", "password": "${DBPassword}", "engine": "mysql", "host": "${target_db_endpoint}", "port": 3306, "dbname": "${target_db}" }',
                            {
                                "TARGET_DB_ENDPOINT": target_db_endpoint,
                                "TARGET_DB": target_db
                            }
                        ]
                    }
                }
            },
            "SourceDataProvider": {
                "Type": "AWS::DMS::DataProvider",
                "Properties": {
                    "DataProviderIdentifier" : f"{source_db}-source",
                    "DataProviderName": f"{source_db}-source",
                    "Engine": "mysql",
                    "Settings": {
                        "MySqlSettings": {
                            "Port" : 3306,
                            "ServerName" : source_db_endpoint,
                            "SslMode" : "none"
                        }
                    },
                }
            },
            "TargetDataProvider": {
                "Type": "AWS::DMS::DataProvider",
                "Properties": {
                    "DataProviderIdentifier" : f"{source_db}-destination",
                    "DataProviderName": f"{source_db}-destination",
                    "Engine": "mysql",
                    "Settings": {
                        "MySqlSettings": {
                            "Port" : 3306,
                            "ServerName" : target_db_endpoint,
                            "SslMode" : "none"
                        }
                    },
                }
            },
            "DMSSubnetGroup": {
                "Type": "AWS::DMS::ReplicationSubnetGroup",
                "Properties": {
                    "ReplicationSubnetGroupIdentifier": f"{source_db}-dms-subnet-group",
                    "ReplicationSubnetGroupDescription": "DMS Subnet Group",
                    "SubnetIds": subnet_ids
                }
            },
            "DMSInstanceProfile": {
                "Type": "AWS::DMS::InstanceProfile",
                "Properties": {
                    "InstanceProfileIdentifier": f"{source_db}-profile",
                    "InstanceProfileName": f"{source_db}-profile",
                    "PubliclyAccessible": False,
                    "NetworkType": "IPV4",
                    "SubnetGroupIdentifier": {"Ref": "DMSSubnetGroup"},
                    "VpcSecurityGroups" : [default_vpc_sg]
                }
            },
            "MigrationProject": {
                "Type": "AWS::DMS::MigrationProject",
                "Properties": {
                    "MigrationProjectIdentifier": f"{source_db}-project",
                    "MigrationProjectName": f"{source_db}-project",
                    "SourceDataProviderDescriptors": [{
                        "DataProviderArn": {"Ref": "SourceDataProvider"},
                        "DataProviderIdentifier": {"Ref": "SourceDataProvider"},
                        "SecretsManagerAccessRoleArn": dms_iam_role,
                        "SecretsManagerSecretId": {"Ref": "SourceSecret"}
                    }],
                    "TargetDataProviderDescriptors": [{
                        "DataProviderArn": {"Ref": "TargetDataProvider"},
                        "DataProviderIdentifier": {"Ref": "TargetDataProvider"},
                        "SecretsManagerAccessRoleArn": dms_iam_role,
                        "SecretsManagerSecretId": {"Ref": "TargetSecret"}
                    }],
                    "InstanceProfileIdentifier": {"Ref": "DMSInstanceProfile"},
                }
            },
            "DataMigration": {
                "Type" : "AWS::DMS::DataMigration",
                "Properties" : {
                    "DataMigrationIdentifier" : f"{source_db}-data-migration",
                    "DataMigrationName" : f"{source_db}-data-migration",
                    "DataMigrationSettings" : {
                        "CloudwatchLogsEnabled" : True,
                        "NumberOfJobs" : 8
                        },
                    "DataMigrationType" : "full-load-and-cdc",
                    "MigrationProjectIdentifier" : {"Ref": "MigrationProject"},
                    "ServiceAccessRoleArn" : dms_iam_role
                    }
            }
        },
    }

    with open(f"{source_db}-dms-migration-template.json", "w") as f:
        json.dump(template, f, indent=2)
    print(f"CloudFormation template written to '{source_db}-dms-migration-template.json'.")
    return f"{source_db}-dms-migration-template.json"

def get_default_security_group(vpc_id, region_name):
    ec2 = boto3.client('ec2', region_name=region_name)

    try:
        response = ec2.describe_security_groups(
            Filters=[
                {'Name': 'vpc-id', 'Values': [vpc_id]},
                {'Name': 'group-name', 'Values': ['default']}
            ]
        )

        if response['SecurityGroups']:
            sg = response['SecurityGroups'][0]
            return sg['GroupId']
        else:
            print(f"No default security group found for VPC {vpc_id}.")
            return None

    except Exception as e:
        print(f"Error fetching security group: {e}")
        return None
    
def get_dms_iam_role_arn():
    iam = boto3.client('iam')
    try:
        response = iam.get_role(RoleName="HomogeneousDataMigrationsRole")
        arn = response['Role']['Arn']
        return arn
    except Exception as e:
        print(f"Error retrieving role ARN: {e}")
        return None

def gather_env_data(db):
    rds = boto3.client('rds', region_name=aws_region)
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db)
        instance = response['DBInstances'][0]

        info = {
            'Endpoint':instance['Endpoint']['Address'],
            'VPC': instance['DBSubnetGroup']['VpcId'],
            'DBSubnets': [instance['DBSubnetGroup']['Subnets'][0]['SubnetIdentifier'],instance['DBSubnetGroup']['Subnets'][1]['SubnetIdentifier']],
        }

        return info

    except Exception as e:
        print(f"Error describing DB instance: {e}")

def upload_template_to_s3(template_path, bucket_name, key_prefix="dms-cf-templates"):
    s3 = boto3.client('s3', region_name=aws_region)
    key = f"{key_prefix}/{template_path}"
    s3.upload_file(template_path, bucket_name, key)
    url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
    return url

if __name__ == "__main__":
    source_rds_info = gather_env_data(source_db)
    target_rds_info = gather_env_data(target_db)
    subnet_ids = source_rds_info['DBSubnets']
    vpc_id = source_rds_info['VPC']
    default_vpc_sg = get_default_security_group(vpc_id, aws_region)
    source_db_endpoint = source_rds_info['Endpoint']
    target_db_endpoint = target_rds_info['Endpoint']
    dms_iam_role = get_dms_iam_role_arn()

    template_file = generate_dms_template()

    cf_template_url = upload_template_to_s3(template_file, s3_bucket)
    if cf_template_url:
        print(f"The Cloudformation template has been uploaded to {cf_template_url}")
    os.remove(template_file)