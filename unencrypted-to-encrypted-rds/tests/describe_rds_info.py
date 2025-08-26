import boto3
import argparse

parser = argparse.ArgumentParser(description="Describe RDS instance")
parser.add_argument('--db', required=True, help='source snapshot')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

# Configuration
AWS_REGION = args.region
DB_INSTANCE_IDENTIFIER = args.db

# Create RDS client
rds = boto3.client('rds', region_name=AWS_REGION)

def describe_rds_instance(instance_id):
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
        instance = response['DBInstances'][0]

        info = {
            'DBInstanceIdentifier': instance['DBInstanceIdentifier'],
            'Endpoint':instance['Endpoint']['Address'],
            'MultiAZ': instance['MultiAZ'],
            'DBInstanceClass': instance['DBInstanceClass'],
            'StorageType': instance['StorageType'],
            'AllocatedStorage (GB)': instance['AllocatedStorage'],
            'DBSubnetGroup': instance['DBSubnetGroup']['DBSubnetGroupName'],
            'DBSubnets': [instance['DBSubnetGroup']['Subnets'][0]['SubnetIdentifier'],instance['DBSubnetGroup']['Subnets'][1]['SubnetIdentifier']],
            'VPC': instance['DBSubnetGroup']['VpcId'],
            'VpcSecurityGroups': [sg['VpcSecurityGroupId'] for sg in instance['VpcSecurityGroups']],
            'DBParameterGroups': [pg['DBParameterGroupName'] for pg in instance['DBParameterGroups']]
        }

        print("\nRDS Instance Info:")
        for key, value in info.items():
            print(f"{key}: {value}")
        return info
    except Exception as e:
        print(f"Error describing DB instance: {e}")

if __name__ == "__main__":
    describe_rds_instance(DB_INSTANCE_IDENTIFIER)
# RDS_INFO = describe_rds_instance(DB_INSTANCE_IDENTIFIER)
# print(type(RDS_INFO))
# print(RDS_INFO['MultiAZ'])
# print(RDS_INFO['DBInstanceClass'])
# print(RDS_INFO['StorageType'])
# print(RDS_INFO['AllocatedStorage (GB)'])
# print(RDS_INFO['VpcSecurityGroups'])
# print(RDS_INFO['DBParameterGroups'])
# print(type(RDS_INFO['DBParameterGroups']))



# for key, value in info.items():
#     print(f"{key}: {value}")
