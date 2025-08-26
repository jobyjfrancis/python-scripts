import boto3

def get_stack_output(stack_name, output_key):
    """
    Retrieves the value of a specified Output key from a CloudFormation stack.

    :param stack_name: Name of the CloudFormation stack
    :param output_key: The key of the output value to retrieve
    :return: The value associated with the output key or None if not found
    """
    cf = boto3.client('cloudformation')

    try:
        response = cf.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        
        outputs = stack.get('Outputs', [])
        for output in outputs:
            if output['OutputKey'] == output_key:
                return output['OutputValue']
        
        print(f"Output key '{output_key}' not found in stack '{stack_name}'.")
        return None

    except Exception as e:
        print(f"Error fetching stack outputs: {e}")
        return None


if __name__ == "__main__":
    # Replace with your stack name and output key
    stack_name = 'cosmos-denver-uat'
    output_key = 'MySQLPassword'

    value = get_stack_output(stack_name, output_key)
    if value:
        print(f"Output value for '{output_key}': {value}")
