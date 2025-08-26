# Usage
# aws-vault exec <account> -- python3 create_encrypted_rds.py --db <cluster>-<stack>-<env> --region <aws-region>

import boto3
import argparse

parser = argparse.ArgumentParser(description="Create encrypted database")
parser.add_argument('--db', required=True, help='database')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()
db_instance_id = args.db
aws_region = args.region

rds = boto3.client('rds', region_name=aws_region)

def create_snapshot(snapshot_id):
    print(f"### Creating snapshot for RDS instance '{db_instance_id}'...")
    try:
        response = rds.create_db_snapshot(
        DBInstanceIdentifier=db_instance_id,
        DBSnapshotIdentifier=snapshot_id
        )
        print(f"Snapshot started: {snapshot_id}")
        return response['DBSnapshot']['DBSnapshotIdentifier']
    except Exception as e:
        print(f"Error creating snapshot: {e}")

def copy_and_encrypt_snapshot(source_id, dest_id, kms_key=None):
    print(f"### Copying and encrypting snapshot '{source_id}' to '{dest_id}'...")
    try:
        copy_params = {
            'SourceDBSnapshotIdentifier': source_id,
            'TargetDBSnapshotIdentifier': dest_id,
            'CopyTags': True,
            'OptionGroupName':'default:mysql-8-0',
            'KmsKeyId':kms_key
        }

        response = rds.copy_db_snapshot(**copy_params)
        print(f"Snapshot copy initiated: {dest_id}")
        return response['DBSnapshot']['DBSnapshotIdentifier']
    except Exception as e:
        print(f"Failed to copy/encrypt snapshot: {e}")

def describe_rds_instance(db_instance_identifier):
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
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
        print(f"### Restoring RDS instance '{new_db_instance_id}' from snapshot '{encrypted_snapshot_id}'...")

        restore_params = {
            'DBInstanceIdentifier': new_db_instance_id,
            'DBSnapshotIdentifier': encrypted_snapshot_id,
            'MultiAZ': multi_az,
            'AvailabilityZone': availability_zone,
            'DBInstanceClass': db_instance_class,
            'PubliclyAccessible': False,
            'StorageType': storage_type,
            'AllocatedStorage': allocated_storage,
            'AutoMinorVersionUpgrade': True,
            'DBParameterGroupName': db_parameter_group,  
            'CopyTagsToSnapshot': True,
        }

        if db_subnet_group_name:
            restore_params['DBSubnetGroupName'] = db_subnet_group_name
        if vpc_security_group_ids:
            restore_params['VpcSecurityGroupIds'] = vpc_security_group_ids

        response = rds.restore_db_instance_from_db_snapshot(**restore_params)
        print(f"Restore initiated. DB Instance ID: {response['DBInstance']['DBInstanceIdentifier']}")
        return response['DBInstance']['DBInstanceIdentifier']
    except Exception as e:
        print(f"Error restoring DB instance: {e}")

def get_rds_kms_arn(region=aws_region):
    kms = boto3.client('kms', region_name=region)
    try:
        response = kms.describe_key(KeyId=f'alias/{db_instance_id}/rds')
        return response['KeyMetadata']['Arn']
    except Exception as e:
        print(f"Error fetching database RDS KMS key: {e}")

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
        print("Encrypted DB instance is now available.\n")
    except Exception as e:
        print(f"Error while waiting: {e}")        

def wait_for_snapshot(snapshot_id, snap_type=None):
    if snap_type != None:
        print(f"Waiting for {snap_type} snapshot '{snapshot_id}' to become available...")
    else:
        print(f"Waiting for snapshot '{snapshot_id}' to become available...")
    waiter = rds.get_waiter('db_snapshot_available')
    try:
        waiter.wait(
            DBSnapshotIdentifier=snapshot_id,
            WaiterConfig={
                'Delay': 30,  
                'MaxAttempts': 20  
            }
        )
        print("Snapshot is now available.\n")
    except Exception as e:
        print(f"Error while waiting for snapshot: {e}")

if __name__ == "__main__":
    snapshot_id = f"{db_instance_id}-snapshot"
    encrypted_snapshot_id = f"{snapshot_id}-encrypted"
    new_db_instance_id = f"{db_instance_id}-encrypted"

    # Take RDS snapshot
    snapshot_id = create_snapshot(snapshot_id)
    if snapshot_id:
        wait_for_snapshot(snapshot_id)

    # Copy snapshot and encrypt
    kms_key_id = get_rds_kms_arn(aws_region)
    copied_snapshot_id = copy_and_encrypt_snapshot(snapshot_id, encrypted_snapshot_id, kms_key_id)
    if copied_snapshot_id:
        wait_for_snapshot(copied_snapshot_id, "encrypted")

    # Restore snapshot to encrypted RDS instance
    rds_info = describe_rds_instance(db_instance_id)
    multi_az = rds_info['MultiAZ']
    availability_zone = rds_info['AvailabilityZone']
    db_instance_class = rds_info['DBInstanceClass']
    storage_type = rds_info['StorageType']
    allocated_storage = rds_info['AllocatedStorage (GB)']
    db_subnet_group_name = rds_info['DBSubnetGroup']
    vpc_security_group_ids = rds_info['VpcSecurityGroups']
    db_parameter_group = ", ".join(rds_info['DBParameterGroups'])

    db_instance_id = restore_db_instance_from_snapshot()
    if db_instance_id:
        wait_for_db_instance(db_instance_id)