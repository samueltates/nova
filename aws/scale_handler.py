import boto3
import time
import os
import asyncio  
from tools.debug import eZprint, eZprint_anything

DEBUG_KEYS = ['AWS', 'SCALE_HANDLER']
# Initialize boto3 clients
ec2_client = boto3.client('ec2', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
asg_client = boto3.client('autoscaling', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
ecs_client = boto3.client('ecs', region_name='us-east-1',aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

async def scale_asg(asg_name, desired_capacity):

    #check if the desired capacity is already set
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name]))
    current_capacity = response['AutoScalingGroups'][0]['DesiredCapacity']
    if current_capacity == desired_capacity:
        eZprint("ASG already at desired capacity.", DEBUG_KEYS)
        return
    
    eZprint("Scaling ASG...", DEBUG_KEYS)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: asg_client.set_desired_capacity(
        AutoScalingGroupName=asg_name,
        DesiredCapacity=desired_capacity,
        HonorCooldown=False
    ))


    # return False

async def check_instance_ready(asg_name):
    eZprint("Checking for ready instance...", DEBUG_KEYS)
    while True:
        loop = asyncio.get_event_loop()
        # response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
        response = await loop.run_in_executor(None, lambda: asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name]))
        instances = response['AutoScalingGroups'][0]['Instances']
        if any(i['LifecycleState'] == 'InService' for i in instances):
            print("Instance ready.")
            break
        await asyncio.sleep(1)

async def scale_ecs_service(service_name, cluster_name, count):

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: ecs_client.describe_services(cluster=cluster_name, services=[service_name]))
    current_count = response['services'][0]['desiredCount']
    if current_count == count:
        eZprint("ECS Service already at desired count.", DEBUG_KEYS)
        return
    
    print("Scaling ECS Service...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None , lambda: ecs_client.update_service(
        cluster=cluster_name,
        service=service_name,
        desiredCount=count
    ))


async def check_task_ready(service_name, cluster_name):
    eZprint("Checking for ready task...", DEBUG_KEYS)
    while True:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: ecs_client.describe_services(cluster=cluster_name, services=[service_name]))
        services = response['services']
        if any(s['runningCount'] for s in services):
            eZprint("Task is now running.", DEBUG_KEYS)
            break
        await asyncio.sleep(1)

async def on_demand_scaling(asg_name, service_name, cluster_name):
    # Scale ASG
    await scale_asg(asg_name, 1)
    await check_instance_ready(asg_name)
    
    # Scale ECS service
    await scale_ecs_service(service_name, cluster_name, 1)
    await check_task_ready(service_name, cluster_name)
    return True

async def run_scale_handler():
    hydra_asg = os.environ.get('ASG')
    lightning_service = os.environ.get('SERVICE')
    ecs_cluster = os.environ.get('CLUSTER')
    # create async loop 
    response = await on_demand_scaling(hydra_asg, lightning_service, ecs_cluster)
    
    return response

# await on_demand_scaling(hydra_asg, lightning_service, ecs_cluster)

async def set_services_to_zero():
    hydra_asg = os.environ.get('ASG')
    lightning_service = os.environ.get('SERVICE')
    ecs_cluster = os.environ.get('CLUSTER')
    await scale_asg(hydra_asg, 0)
    await check_instance_ready(hydra_asg)
    
    # Scale ECS service
    await scale_ecs_service(lightning_service, ecs_cluster, 0)
    # await check_task_ready(lightning_service, ecs_cluster)
    return True

if __name__ == "__main__":
    set_services_to_zero()