# Usage
# aws-vault exec <account> -- python3 create_iam_role_and_policy.py

import boto3
import json
from botocore.exceptions import ClientError

iam = boto3.client('iam')

# https://docs.aws.amazon.com/dms/latest/userguide/dm-iam-resources.html

# Create the IAM policy
def create_iam_policy(policy_document):
    try:
        response = iam.create_policy(
            PolicyName="HomogeneousDataMigrationsPolicy",
            PolicyDocument=json.dumps(policy_document),
            Description='Homogeneous Data Migrations Policy'
            )
        return response
    except iam.exceptions.EntityAlreadyExistsException as e:
        print("The IAM policy already exists")
    except ClientError as e:
          print(f"Failed to create policy: {e}")
    
# Create the IAM role
def create_iam_role(assumed_role_policy_document):
    try:
        response = iam.create_role(
            RoleName='HomogeneousDataMigrationsRole',
            AssumeRolePolicyDocument=json.dumps(assumed_role_policy_document),
            Description='Homogeneous Data Migrations Role',
            MaxSessionDuration=3600
        )
        return response
    except iam.exceptions.EntityAlreadyExistsException as e:
        print("The IAM Role already exists")
    except ClientError as e:
          print(f"Failed to create policy: {e}")

# Attach policy to role
def attach_policy_to_iam_role(iam_policy_arn):
    try:
        iam.attach_role_policy(
            RoleName='HomogeneousDataMigrationsRole',
            PolicyArn=iam_policy_arn
        )  
    except ClientError as e:
        print(f"Failed to attach policy: {e}")  

if __name__ == "__main__":
    iam_policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeRouteTables",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeVpcPeeringConnections",
                "ec2:DescribeVpcs",
                "ec2:DescribePrefixLists",
                "logs:DescribeLogGroups"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "servicequotas:GetServiceQuota"
            ],
            "Resource": "arn:aws:servicequotas:*:*:vpc/L-0EA8095F"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:DescribeLogStreams"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:dms-data-migration-*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:log-group:dms-data-migration-*:log-stream:dms-data-migration-*"
        },
        {
            "Effect": "Allow",
            "Action": "cloudwatch:PutMetricData",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateRoute",
                "ec2:DeleteRoute"
            ],
            "Resource": "arn:aws:ec2:*:*:route-table/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateTags"
            ],
            "Resource": [
                "arn:aws:ec2:*:*:security-group/*",
                "arn:aws:ec2:*:*:security-group-rule/*",
                "arn:aws:ec2:*:*:route-table/*",
                "arn:aws:ec2:*:*:vpc-peering-connection/*",
                "arn:aws:ec2:*:*:vpc/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:AuthorizeSecurityGroupIngress"
            ],
            "Resource": "arn:aws:ec2:*:*:security-group-rule/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupIngress"
            ],
            "Resource": "arn:aws:ec2:*:*:security-group/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:AcceptVpcPeeringConnection",
                "ec2:ModifyVpcPeeringConnectionOptions"
            ],
            "Resource": "arn:aws:ec2:*:*:vpc-peering-connection/*"
        },
        {
            "Effect": "Allow",
            "Action": "ec2:AcceptVpcPeeringConnection",
            "Resource": "arn:aws:ec2:*:*:vpc/*"
        }
    ]
}
    
    assumed_role_policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    "dms-data-migrations.amazonaws.com",
                    "dms.ap-southeast-2.amazonaws.com"
                ]
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
    
    
    dms_iam_policy = create_iam_policy(iam_policy_document)
    if dms_iam_policy != None:
        print(f"Created IAM policy {dms_iam_policy['Policy']['PolicyName']}")
        dms_iam_policy_arn = dms_iam_policy['Policy']['Arn']
    else:
        iam_policies = iam.list_policies(
            Scope='Local',
        )
        for policy in iam_policies['Policies']:
            if policy['PolicyName'] == "HomogeneousDataMigrationsPolicy":
                dms_iam_policy_arn = policy['Arn']
                        
    managed_policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
    
    dms_iam_role = create_iam_role(assumed_role_policy_document)
    if dms_iam_role != None:
        attach_policy_to_iam_role(dms_iam_policy_arn)
        attach_policy_to_iam_role(managed_policy_arn)
        print(f"Created IAM Role {dms_iam_role['Role']['RoleName']} with required policies")
    else:
        attach_policy_to_iam_role(dms_iam_policy_arn)
        attach_policy_to_iam_role(managed_policy_arn)
        print(f"Attached required policies to role HomogeneousDataMigrationsRole")