# Usage
# aws-vault exec <account> -- python3 cf_changes.py --stack <cluster>-<stack>-<env> --bucket <s3-bucket> --region <aws-region>

import json
import boto3
import argparse
import os
import time
from collections import OrderedDict

parser = argparse.ArgumentParser(description="Cloudformation changes and resource import")
parser.add_argument('--stack', required=True, help='CF stack cluster-stack-env')
parser.add_argument('--bucket', required=True, help='S3 bucket to store the CF templates')
parser.add_argument('--region', required=True, help='region')

args = parser.parse_args()

cf_stack = args.stack
s3_bucket = args.bucket
aws_region = args.region

cf = boto3.client('cloudformation', region_name=aws_region)

def get_stack(stack_name):
    try:
        response = cf.describe_stacks(
        StackName=stack_name
        )
        return response['Stacks'][0]
    except:
        return None
        
def get_current_stack_template(stack_name):
    try:
        response = cf.get_template(
            StackName=stack_name,
            TemplateStage='Original'  
        )
        template_body = response['TemplateBody']
        return template_body
    except Exception as e:
        print("Couldn't fetch template:", e)
        return None

def modify_stack_template(cf_template):
    cf_template['Resources']['MySQLServer']['DeletionPolicy'] = "Retain"
    return cf_template

def upload_template_to_s3(template_file, bucket_name, key_prefix="rds-encryption-cf-templates"):
    s3 = boto3.client('s3', region_name=aws_region)
    key = f"{key_prefix}/{template_file}"
    s3.upload_file(template_file, bucket_name, key)
    url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
    return url

def download_template_from_s3(template_file, bucket_name, local_file, key_prefix="rds-encryption-cf-templates"):
    s3 = boto3.client('s3', region_name=aws_region)
    key = f"{key_prefix}/{template_file}"
    s3.download_file(bucket_name, key, local_file)

def check_s3_file_exists(bucket, template_path,  key_prefix="rds-encryption-cf-templates"):
    try:
        s3 = boto3.client('s3', region_name = aws_region)
        response = s3.get_object(
            Bucket=bucket,
            Key=f"{key_prefix}/{template_path}",
        )
        return response
    except:
        return None

def update_stack(stack_name, stack, template_url):
    try:
            cf.update_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=stack['Parameters'],
            Capabilities=['CAPABILITY_IAM'],
            Tags=stack['Tags'],
            DisableRollback=stack['DisableRollback']
            )
    except Exception as e:
        raise e
    
    try:
        print("Waiting for stack update to finish...")
        waiter = cf.get_waiter('stack_update_complete')
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 20}
        )
        print("Stack update completed\n")
    except Exception as e:
        raise e
    
def remove_mysql_resource_from_template(cf_template):
    resources_to_remove = ["MySQLServer", "RDSCPUCreditBalanceAlarm", "RDSLowDiskSpaceAlarm"]
    for resource in resources_to_remove:
        if resource in cf_template["Resources"]:
            del cf_template["Resources"][resource]

    output_to_remove = "MySQLEndpoint"     
    if output_to_remove in cf_template['Outputs']:
        del cf_template["Outputs"][output_to_remove]   
            
    return cf_template   

def add_resources_output_to_template(cf_template, original_template):
    resources_to_add = ["RDSCPUCreditBalanceAlarm", "RDSLowDiskSpaceAlarm"]
    output_to_add = "MySQLEndpoint"

    for resource in resources_to_add:
        original_resource = original_template['Resources'][resource]
        original_resource['Properties']['Dimensions'][0]['Value']['Fn::Join'][1].insert(3, "encrypted")
        cf_template['Resources'][resource] = original_resource

    cf_template['Outputs'][output_to_add] = {"Value": {"Fn::GetAtt": ["MySQLServer", "Endpoint.Address"]}}
    return cf_template

def inject_rds_resource(template, rds_resource_name, rds_resource_definition, after_resource_name=None):
    resources = template.get('Resources')
    new_resources = OrderedDict()
    inserted = False

    for key, value in resources.items():
        new_resources[key] = value
        if key == after_resource_name:
            new_resources[rds_resource_name] = rds_resource_definition
            inserted = True

    if not inserted:
        new_resources[rds_resource_name] = rds_resource_definition

    template['Resources'] = new_resources
    return template    

def create_import_changeset(stack, stack_name, template_url, resources_to_import):
    change_set_name = f"import-changeset"
    print(f"Creating change set: {change_set_name}")
    
    cf.create_change_set(
        StackName=stack_name,
        ChangeSetName=change_set_name,
        ChangeSetType='IMPORT',
        ResourcesToImport=resources_to_import,
        TemplateURL=template_url,
        Parameters=stack['Parameters'],
        Capabilities=['CAPABILITY_IAM'],
        Tags=stack['Tags']
    )

    print("Waiting for change set to be created...")
    waiter = cf.get_waiter('change_set_create_complete')
    try:
        waiter.wait(
            ChangeSetName=change_set_name,
            StackName=stack_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 20}
        )
    except Exception as e:
        print("Change set creation failed:", e)
        return None

    return change_set_name

def execute_import_changeset(stack_name, change_set_name):
    print(f"Executing change set: {change_set_name}")
    cf.execute_change_set(
        ChangeSetName=change_set_name,
        StackName=stack_name
    )
    print("Waiting for import to complete...")
    waiter = cf.get_waiter('stack_import_complete')
    try:
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={'Delay': 10, 'MaxAttempts': 30}
        )
        print("Import completed successfully.\n")
    except Exception as e:
        print("Change set execution failed:", e)
        return None          

if __name__ == "__main__":
    # Get the original stack details before starting the update operations
    stack = get_stack(cf_stack)

    # Download the current original template and save it in S3 - check if template already exists in S3
    print("### Fetching the current CF template...")
    template_exist = check_s3_file_exists(s3_bucket, f"{cf_stack}-original.json")
    if template_exist == None:
        current_template = get_current_stack_template(cf_stack)
        current_template_json = json.dumps(current_template, indent=2)
        with open(f"{cf_stack}-original.json", "w") as f:
            f.write(current_template_json)
        upload_template_to_s3(f"{cf_stack}-original.json", s3_bucket)
        os.remove(f"{cf_stack}-original.json")
        print(f"CF template has been fetched and saved in S3 bucket {s3_bucket}/rds-encryption-cf-templates\n")
        time.sleep(3)
    else:
        print("The current CF template already exists in S3 bucket, proceeding to next step...\n")   
        time.sleep(3)     

    # Update the template to set DeletionPolicy to Retain for MySQLServer resource
    print("### Updating the CF template to set DeletionPolicy to Retain for resource MySQLServer...")
    current_template = get_current_stack_template(cf_stack)
    updated_template = modify_stack_template(current_template)
    updated_template_json = json.dumps(updated_template, indent=2)
    with open(f"{cf_stack}-rds-retain.json", "w") as f:
        f.write(updated_template_json)
    cf_template_url = upload_template_to_s3(f"{cf_stack}-rds-retain.json", s3_bucket)
    os.remove(f"{cf_stack}-rds-retain.json")
    print("CF template updated")
    time.sleep(3)
    # Run Cloudformation Update to set DeletionPolicy to Retain
    print("Running the CF Update to set DeletionPolicy to Retain for MySQLServer...")
    update_stack(cf_stack, stack, cf_template_url)

    # Update the template to remove the MySQLServer resource
    print("### Updating the CF template to remove the original unencrypted MySQLServer resource and dependencies...")
    current_template_with_retain = get_current_stack_template(cf_stack)
    updated_template_mysql_removed = remove_mysql_resource_from_template(current_template_with_retain)
    updated_template_mysql_removed_json = json.dumps(updated_template_mysql_removed, indent=2)
    with open(f"{cf_stack}-rds-remove.json", "w") as f:
        f.write(updated_template_mysql_removed_json)
    cf_template_url = upload_template_to_s3(f"{cf_stack}-rds-remove.json", s3_bucket)
    os.remove(f"{cf_stack}-rds-remove.json")
    print("CF template updated")
    time.sleep(3)
    # Run Cloudformation Update to remove unencrypted MySQLServer resource
    print("Running the CF Update to remove unencrypted MySQLServer resource and dependencies...")
    update_stack(cf_stack, stack, cf_template_url)

    # Import the new encrypted MySQL resource into Cloudformation
    print("### Importing new encrypted RDS resource into Cloudformation...")
    print("Creating the CF template for import operation....")
    time.sleep(3)

    current_template_after_rds_removed = get_current_stack_template(cf_stack)
    rds_resource_name = "MySQLServer"

    download_template_from_s3(f"{cf_stack}-original.json", s3_bucket, f"{cf_stack}-original.json")
    with open(f"{cf_stack}-original.json", "r") as f:
            import_template = json.loads(f.read())
    import_template['Resources']['MySQLServer']['DeletionPolicy'] = "Retain"
    import_template['Resources']['MySQLServer']['Properties']['StorageEncrypted'] = True
    import_template['Resources']['MySQLServer']['Properties']['DBInstanceIdentifier']['Fn::Join'][1].insert(3, "encrypted")
    os.remove(f"{cf_stack}-original.json")
    
    rds_resource_definition = import_template['Resources']['MySQLServer']
    resource_to_import = [
        {
        "ResourceType": "AWS::RDS::DBInstance",
        "LogicalResourceId": rds_resource_name,
        "ResourceIdentifier": {
            "DBInstanceIdentifier": f"{cf_stack}-encrypted"
            }
        }
    ]

    after_resource_name = "RdsSecGroup"
    updated_template_with_new_rds = inject_rds_resource(current_template_after_rds_removed, rds_resource_name, rds_resource_definition, after_resource_name)
    updated_template_with_new_rds_json = json.dumps(updated_template_with_new_rds, indent=2)
    with open(f"{cf_stack}-rds-import.json", "w") as f:
        f.write(updated_template_with_new_rds_json)
    cf_template_url = upload_template_to_s3(f"{cf_stack}-rds-import.json", s3_bucket)
    os.remove(f"{cf_stack}-rds-import.json")
    print("CF template for import operation has been created...")
    time.sleep(3)
    
    # Create import change set 
    import_resource_change_set = create_import_changeset(stack, cf_stack, cf_template_url, resource_to_import)
    # Execute changeset to import encrypted RDS
    if import_resource_change_set:
        execute_import_changeset(cf_stack, import_resource_change_set)

    # Update dependencies - Add resources for "RDSCPUCreditBalanceAlarm", "RDSLowDiskSpaceAlarm" and the output "MySQLEndpoint"  
    print("### Updating the CF template to add dependent resources and output...")
    current_template_with_new_rds = get_current_stack_template(cf_stack)
    download_template_from_s3(f"{cf_stack}-original.json", s3_bucket, f"{cf_stack}-original.json")
    with open(f"{cf_stack}-original.json", "r") as f:
            original_template = json.loads(f.read())

    updated_template_deps_added = add_resources_output_to_template(current_template_with_new_rds, original_template)
    updated_template_deps_added_json = json.dumps(updated_template_deps_added, indent=2)
    with open(f"{cf_stack}-rds-update-deps.json", "w") as f:
        f.write(updated_template_deps_added_json)
    cf_template_url = upload_template_to_s3(f"{cf_stack}-rds-update-deps.json", s3_bucket)
    os.remove(f"{cf_stack}-rds-update-deps.json")
    os.remove(f"{cf_stack}-original.json")
    print("CF template updated")
    time.sleep(3)
    # Run Cloudformation Update to add cloudwatch alarm resources and output that relates to RDS
    print("Running the CF Update to add dependent resources and output...")
    update_stack(cf_stack, stack, cf_template_url)