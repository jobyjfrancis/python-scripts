# Usage
# aws-vault exec <account> -- python3 restore_rds_snapshot.py --sourcedb <cluster>-<stack>-<env> --region <aws-region>

import boto3
import argparse

parser = argparse.ArgumentParser(description="Restore RDS snapshot")
parser.add_argument('--sourcedb', required=True, help='source snapshot')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

SOURCE_DB = args.sourcedb
AWS_REGION = args.region

SNAPSHOT_IDENTIFIER = f"{SOURCE_DB}-snapshot-encrypted"
NEW_DB_INSTANCE_ID = f"{SOURCE_DB}-encrypted"

rds = boto3.client('rds', region_name=AWS_REGION)

def describe_rds_instance(SOURCE_DB):
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=SOURCE_DB)
        instance = response['DBInstances'][0]

        info = {
            'DBInstanceIdentifier': instance['DBInstanceIdentifier'],
            'MultiAZ': instance['MultiAZ'],
            'AvailabilityZone': instance['AvailabilityZone'],
            'DBInstanceClass': instance['DBInstanceClass'],
            'StorageType': instance['StorageType'],
            'AllocatedStorage (GB)': instance['AllocatedStorage'],
            'VPC': instance['DBSubnetGroup']['VpcId'],
            'DBSubnetGroup': instance['DBSubnetGroup']['DBSubnetGroupName'],
            'VpcSecurityGroups': [sg['VpcSecurityGroupId'] for sg in instance['VpcSecurityGroups']],
            'DBParameterGroups': [pg['DBParameterGroupName'] for pg in instance['DBParameterGroups']]
        }

        return info

    except Exception as e:
        print(f"Error describing DB instance: {e}")


def restore_db_instance_from_snapshot():
    try:
        print(f"Restoring RDS instance '{NEW_DB_INSTANCE_ID}' from snapshot '{SNAPSHOT_IDENTIFIER}'...")

        restore_params = {
            'DBInstanceIdentifier': NEW_DB_INSTANCE_ID,
            'DBSnapshotIdentifier': SNAPSHOT_IDENTIFIER,
            'MultiAZ': MULTI_AZ,
            'AvailabilityZone': AVAILABILITY_ZONE,
            'DBInstanceClass': DB_INSTANCE_CLASS,
            'PubliclyAccessible': False,
            'StorageType': STORAGE_TYPE,
            'AllocatedStorage': ALLOCATED_STORAGE,
            'AutoMinorVersionUpgrade': True,
            'DBParameterGroupName': DB_PARAMETER_GROUP,  
            'CopyTagsToSnapshot': True,
        }

        if DB_SUBNET_GROUP_NAME:
            restore_params['DBSubnetGroupName'] = DB_SUBNET_GROUP_NAME
        if VPC_SECURITY_GROUP_IDS:
            restore_params['VpcSecurityGroupIds'] = VPC_SECURITY_GROUP_IDS

        response = rds.restore_db_instance_from_db_snapshot(**restore_params)
        print(f"Restore initiated. DB Instance ID: {response['DBInstance']['DBInstanceIdentifier']}")
        return response['DBInstance']['DBInstanceIdentifier']
        # print("Monitor the progress and check in AWS console")
    except Exception as e:
        print(f"Error restoring DB instance: {e}")

def wait_for_db_instance(db_instance_id):
    print(f"Waiting for encrypted DB instance '{db_instance_id}' to become available...")
    waiter = rds.get_waiter('db_instance_available')
    try:
        waiter.wait(
            DBInstanceIdentifier=db_instance_id,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 20
            }
        )
        print("Encrypted DB instance is now available.")
    except Exception as e:
        print(f"Error while waiting: {e}")        

if __name__ == '__main__':
    RDS_INFO = describe_rds_instance(SOURCE_DB)
    MULTI_AZ = RDS_INFO['MultiAZ']
    AVAILABILITY_ZONE = RDS_INFO['AvailabilityZone']
    DB_INSTANCE_CLASS = RDS_INFO['DBInstanceClass']
    STORAGE_TYPE = RDS_INFO['StorageType']
    ALLOCATED_STORAGE = RDS_INFO['AllocatedStorage (GB)']
    DB_SUBNET_GROUP_NAME = RDS_INFO['DBSubnetGroup']
    VPC_SECURITY_GROUP_IDS = RDS_INFO['VpcSecurityGroups']
    DB_PARAMETER_GROUP = ", ".join(RDS_INFO['DBParameterGroups'])

    db_instance_id = restore_db_instance_from_snapshot()
    if db_instance_id:
        wait_for_db_instance(db_instance_id)
