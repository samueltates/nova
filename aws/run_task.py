import boto3
import time
import socket
import requests
import asyncio
# from tools.debug import eZprint
# 
#  
# from session.appHandler import app
import os

elb_client = boto3.client('elbv2', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
asg_client = boto3.client('autoscaling', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
ecs_client = boto3.client('ecs', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
service_discovery = boto3.client('servicediscovery', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

DEBUG_KEYS = ['AWS', 'RUN_TASK']

instances_added = []
tasks_added = []
# print = None
async def check_task_cpu_usage(task_name):
    response = ecs_client.describe_tasks(
        cluster='default',
        tasks=[task_name]
    )
    task_cpu = response['tasks'][0]['cpu']
    print(f"Task CPU: {task_cpu}", DEBUG_KEYS)
    return task_cpu

async def check_capacity_cpu(capacity_provider):
    # response = asg_client.describe_auto_scaling_groups(
    #     AutoScalingGroupNames=[asg_name]
    # )
    # current_capacity = response['AutoScalingGroups'][0]['DesiredCapacity']
    # eZprint(f"Current ASG Capacity: {current_capacity}", DEBUG_KEYS)
    
    #get instances with capacity provider "rolla_dex" and get their CPU usage

    response = ecs_client.list_container_instances(
        cluster='default',
        # filter=f'attribute:capacity-provider=={capacity_provider}'
    )
    print(response, DEBUG_KEYS)
    container_instances = response['containerInstanceArns']
    print(f"Container Instances: {container_instances}", DEBUG_KEYS)

    total_cpu = 0
    for instance in container_instances:
        response = ecs_client.describe_container_instances(
            cluster='default',
            containerInstances=[instance]
        )
        cpu = response['containerInstances'][0]['remainingResources'][0]['integerValue']
        total_cpu += cpu

    print(f"Total CPU Usage: {total_cpu}", DEBUG_KEYS)


    return total_cpu


async def set_asg_capacity(asg_name, desired_capacity):

    # get current capacity
    response = asg_client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )

    response = asg_client.set_desired_capacity(
        AutoScalingGroupName=asg_name,
        DesiredCapacity=desired_capacity,
        HonorCooldown=False
    )

    print(f"Set desired capacity to {desired_capacity} for ASG {asg_name}.", DEBUG_KEYS)
    
    #await for instances to be added

    response = asg_client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )
    instance = response['AutoScalingGroups'][-1]['Instances']
    
    while instance[0]['LifecycleState'] != 'InService':
        time.sleep(1)
        response = asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )
        instance = response['AutoScalingGroups'][-1]['Instances']
        
    return instance

async def set_total_tasks_per_service(service_name, desired_count):
    response = ecs_client.update_service(
        cluster='default',
        service=service_name,
        desiredCount=desired_count
    )

    print(f"Set desired count to {desired_count} for service {service_name}.", DEBUG_KEYS)
    return response


async def run_and_register_task():
    response = ecs_client.run_task(
        cluster='default',
        taskDefinition='rendering:42',
        launchType='EC2',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [
                    'subnet-0e2208a3c08aa7d54',
                    'subnet-0577d0375fdecb35c',
                    'subnet-0ba506eb8456a5b27'
                ],
                'securityGroups': ['sg-080f878cf5d1de129'],
                'assignPublicIp': 'DISABLED'
            }
        },
        count=1
    )
    print(response)
    time.sleep(10)
    task_arn = response['tasks'][-1]['taskArn']
    print(f"Launched task ARN: {task_arn}", DEBUG_KEYS)

    describe_response = ecs_client.describe_tasks(
        cluster='default', tasks=[task_arn])
    eni_id = [att['value'] for att in describe_response['tasks'][0]
              ['attachments'][0]['details'] if att['name'] == 'networkInterfaceId'][0]
    print(f'ENI ID: {eni_id}', DEBUG_KEYS)

    eni_response = ec2_client.describe_network_interfaces(
        NetworkInterfaceIds=[eni_id]
    )
    private_ip = eni_response['NetworkInterfaces'][0]['PrivateIpAddress']
    print(f"Private IP: {private_ip}", DEBUG_KEYS)

    # tasks_added.append(task_arn)

    return task_arn, private_ip

async def poll_task_status(task_arn):
    while True:
        response = ecs_client.describe_tasks(
            cluster='default', tasks=[task_arn])
        task_status = response['tasks'][0]['lastStatus']
        print(f"Task Status: {task_status}", DEBUG_KEYS)

        if task_status == 'STOPPED':
            break
        time.sleep(5)

async def poll_instance_health(asg_name):
    while True:
        response = asg_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name])
        instances = response['AutoScalingGroups'][0]['Instances']
        healthy_count = sum(
            1 for i in instances if i['LifecycleState'] == 'InService')
        total_count = len(instances)
        print(f"Healthy Instances: {healthy_count}/{total_count}", DEBUG_KEYS)

        if healthy_count == total_count:
            break
        time.sleep(10)

        # Register Task with Service Discovery
async def register_task_with_service_discovery(task_arn, private_ip, service_id):

    register_response = service_discovery.register_instance(
        ServiceId=service_id,
        InstanceId=task_arn.split("/")[-1],
        Attributes={
            'AWS_INSTANCE_IPV4': private_ip,
            # 'AWS_ALIAS_DNS_NAME': 'renderer.aws-development-api.asknova.ai',
            'TASK_ID': task_arn.split("/")[-1],
            'AWS_INSTANCE_PORT' : '5501'
        }
    )

    print(f'Registered instance with ID: {register_response["OperationId"]}')
    print(f"Instance ID: {task_arn.split('/')[-1]}")
    return task_arn.split("/")[-1]

# Send Request to Task
async def send_request_to_task(resolved_ip):
    endpoint = f"http://{resolved_ip}/your-endpoint"
    response = requests.get(endpoint)
    print(f"Response from task: {response.json()}", DEBUG_KEYS)


# Resolve DNS
async def resolve_dns(namespace, service_name, instance_id):
    hostname = f"{instance_id}.{service_name}.{namespace}"
    print(f"Resolving DNS for: {hostname}")
    try:
        resolved_ip = socket.gethostbyname(hostname)
        print(f"Resolved IP: {resolved_ip}", DEBUG_KEYS)
        return resolved_ip
    except socket.gaierror as e:
        print(f"DNS resolution error: {e}", DEBUG_KEYS)
        return None



# import boto3
async def register_with_target_group(target_group_arn, private_ip, port):
    response = elb_client.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[
            {
                'Id': private_ip,
                'Port': port
            },
        ]
    )
    print(f"Registered task with target group: {response}")
    return response
# servicediscovery = boto3.client('servicediscovery', region_name='us-east-1')

async def stop_task(task_arn):
    response = ecs_client.stop_task(
        cluster='default',
        task=task_arn,
        reason='Task stopped by user'
    )
    print(f"Stopped task {task_arn}.", DEBUG_KEYS)
    return response

async def stop_instance(instance_id):
    response = ec2_client.terminate_instances(
        InstanceIds=[instance_id]
    )
    print(f"Terminated instance {instance_id}.", DEBUG_KEYS)
    return response

async def deregister_task_from_service_discovery(task_id, service_id):
    response = service_discovery.deregister_instance(
        ServiceId=service_id,
        InstanceId=task_id
    )
    print(f"Deregistered task {task_id} from service discovery.", DEBUG_KEYS)
    return response

async def deregister_instance_from_target_group(target_group_arn, instance_id):
    response = elb_client.deregister_targets(
        TargetGroupArn=target_group_arn,
        Targets=[
            {
                'Id': instance_id
            }
        ]
    )
    print(f"Deregistered instance {instance_id} from target group.", DEBUG_KEYS)
    return response


async def list_instances(service_id):
    response = service_discovery.list_instances(ServiceId=service_id)
    print(response, DEBUG_KEYS)

# List all services in the namespace
async def list_services(namespace_id):
    response = service_discovery.list_services(
        Filters=[
            {
                'Name': 'NAMESPACE_ID',
                'Values': [namespace_id],
                'Condition': 'EQ'
            }
        ]
    )
    for service in response['Services']:
        print(f"Service Name: {service['Name']}, Service ID: {service['Id']}", DEBUG_KEYS)


route53 = boto3.client('route53', region_name='us-east-1')

        # List all DNS records in the hosted zone
async def list_dns_records(hosted_zone_id):
    paginator = route53.get_paginator('list_resource_record_sets')
    page_iterator = paginator.paginate(HostedZoneId=hosted_zone_id)

    for page in page_iterator:
        for record_set in page['ResourceRecordSets']:
            print(f"Record Name: {record_set['Name']}, Type: {record_set['Type']}, Value(s): {record_set['ResourceRecords']}", DEBUG_KEYS)

# Use the correct hosted zone ID for your domain

#arg parse


import argparse

target_group_arn = 'arn:aws:elasticloadbalancing:us-east-1:914796322262:targetgroup/the-buzz/f3f5ac77703672d6'

# #close running tasks and instances on exit
# def close():
#     #get tasks 
#     #get instances

async def run_task():

        asg_name = 'hydra'
        capacity_provider = 'rolla_dex'

        # check task cpu required
        # task_cpu = await check_task_cpu_usage(task_arn)

        # check current capacity
        available_cpu = await check_capacity_cpu(capacity_provider)
        instance_id = None
        # increase capacity if required
        if 4096 > available_cpu:

        # Increase ASG capacity
            instance_id = await set_asg_capacity(asg_name)

        # Poll instance health
        # poll_instance_health(asg_name)




        # Run task and register
        task_arn, private_ip = await run_and_register_task()
        # Step 2: Register the task with service discovery
        
        service_id = 'srv-4cy34okuol2i3soz'
        instance_id =  await register_task_with_service_discovery(task_arn, private_ip, service_id)

        await list_instances(service_id)

        await register_with_target_group(target_group_arn, private_ip, 5501)

        # Step 3: Resolve the DNS for the task
        namespace = 'nova-tasks'
        service_name = 'lightning'
        try:
            resolved_ip = await resolve_dns(namespace, service_name, instance_id)
        except Exception as e:
            print(f"Error: {e}")
            resolved_ip = None

            
        await stop_task(task_arn)

        if instance_id:
            await stop_instance(instance_id)
        await deregister_task_from_service_discovery(instance_id, service_id)
        await deregister_instance_from_target_group(target_group_arn, private_ip)



        return {
            'resolved_ip': resolved_ip,
            'private_ip': private_ip,
            'task_arn': task_arn,
            'instance_id': instance_id
        }
        # Step 4: Send request to the task
        # send_request_to_task(resolved_ip)

        # Poll task status
        # poll_task_status(task_arn)


async def run_test():
    resolved_ip = await run_task()
    return resolved_ip




async def set_tasks_required(desired_count):
    service_name = 'nova-lightning'
    # Scale ECS service
    response = await set_total_tasks_per_service(service_name, desired_count)
    return response

if __name__ == '__main__':

    #take args to choose which function tree to run



    parser = argparse.ArgumentParser(description='Run ECS task and resolve DNS for service discovery.')
    
    parser.add_argument('--action', type=str, required=True, help='Action to perform')
    # parser.add_argument('--task-def', type=str, required=True, help='ECS task definition name')
    # parser.add_argument('--cluster', type=str, required=True, help='ECS cluster name')
    # parser.add_argument('--endpoint', type=str, required=True, help='Service endpoint for the task')

    args = parser.parse_args()

    # Run task and register

    ## Run task and register
    if args.action == 'run_task':
        # task_arn, private_ip = run_and_register_task(args.task_def, args.cluster)

        asg_name = 'hydra'
        desired_capacity = 2  # Example desired capacity

        # Increase ASG capacity
        # increase_asg_capacity(asg_name, desired_capacity)

        # Poll instance health
        # poll_instance_health(asg_name)

        # Run task and register
        task_arn, private_ip = run_and_register_task()
        # Step 2: Register the task with service discovery
        
        service_id = 'srv-fzwdugrgmplmanzr'
        instance_id = register_task_with_service_discovery(task_arn, private_ip, service_id)

        # list_instances(service_id)

        # register_with_target_group(target_group_arn, private_ip, 5501)

        # Step 3: Resolve the DNS for the task
        namespace = 'nova-tasks'
        service_name = 'lightning'
        try:
            resolved_ip = resolve_dns(namespace, service_name, instance_id)
        except Exception as e:
            print(f"Error: {e}")
            resolved_ip = None

        stop_task(task_arn)
        stop_instance(instance_id)
        deregister_task_from_service_discovery(instance_id, service_id)
        deregister_instance_from_target_group(target_group_arn, private_ip)


            

        # Step 4: Send request to the task
        send_request_to_task(resolved_ip)

        # Poll task status
        # poll_task_status(task_arn)

    if args.action == 'list_everything':
        service_id = 'srv-fzwdugrgmplmanzr'
        list_instances(service_id)
        namespace_id = 'ns-5v4z7x4zj2q7m6qj'
        list_services(namespace_id)

        # Verify namespace details
        namespace_response = service_discovery.get_namespace(
            Id='ns-e3y7eghjyu6spzwq'  # Use the correct namespace ID
        )
        print(namespace_response)

        # Verify service details
        service_response = service_discovery.get_service(
            Id='srv-fzwdugrgmplmanzr'  # Use the correct service ID
        )
        print(service_response)

        hosted_zone_id = 'Z03997702O9OLOFL2TQIV'
        list_dns_records(hosted_zone_id)

    if args.action == 'resolve_dns':
        namespace = 'aws-development-api.asknova.ai'
        service_name = 'renderer'
        instance_id = '8f5347889440485a8948233a7687f3ed'
        resolved_ip = resolve_dns(namespace, service_name, instance_id)
        send_request_to_task(resolved_ip)
    if args.action == 'stop_task':
        task_arn = 'arn:aws:ecs:us-east-1:914796322262:task/default/83b7ebc81712489e85d9dc4bc174ca0e'
        stop_task(task_arn)
    if args.action == 'set_asg_capacity':
        desired_capacity = 0
        asg_name = 'hydra'
        asyncio.run( set_asg_capacity(asg_name, desired_capacity))
    if args.action == 'set_tasks_required':
        desired_count = 0
        asyncio.run(set_tasks_required(desired_count))