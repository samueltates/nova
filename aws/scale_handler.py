import boto3
import time

# Initialize boto3 clients
ec2_client = boto3.client('ec2')
asg_client = boto3.client('autoscaling')
ecs_client = boto3.client('ecs')

def scale_asg(asg_name, desired_capacity):

    #check if the desired capacity is already set
    response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    current_capacity = response['AutoScalingGroups'][0]['DesiredCapacity']
    if current_capacity >= desired_capacity:
        print("ASG already at desired capacity.")
        return True
    
    print("Scaling ASG...")

    asg_client.set_desired_capacity(
        AutoScalingGroupName=asg_name,
        DesiredCapacity=desired_capacity,
        HonorCooldown=False
    )

    return False

def check_instance_ready(asg_name):
    print("Checking for ready instance...")
    while True:
        response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
        instances = response['AutoScalingGroups'][0]['Instances']
        if any(i['LifecycleState'] == 'InService' for i in instances):
            print("Instance ready.")
            break
        time.sleep(10)

def scale_ecs_service(service_name, cluster_name, count):

    # #get services list
    # response = ecs_client.list_services(
    #     cluster=cluster_name
    # )

    # print(response)

    #check if the desired count is already set
    response = ecs_client.describe_services(
        cluster=cluster_name,
        services=[service_name]
    )
    current_count = response['services'][0]['desiredCount']
    if current_count >= count:
        print("ECS Service already at desired count.")
        return
    
    print("Scaling ECS Service...")
    ecs_client.update_service(
        cluster=cluster_name,
        service=service_name,
        desiredCount=count
    )

def check_task_ready(service_name, cluster_name):
    print("Checking for ready task...")
    while True:
        response = ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )
        services = response['services']
        if any(s['runningCount'] for s in services):
            print("Task is now running.")
            break
        time.sleep(10)

def on_demand_scaling(asg_name, service_name, cluster_name):
    # Scale ASG
    already_running = scale_asg(asg_name, 1)
    if already_running:
        return
    check_instance_ready(asg_name)
    
    # Scale ECS service
    scale_ecs_service(service_name, cluster_name, 1)
    check_task_ready(service_name, cluster_name)

def run_scale_handler():
    hydra_asg = 'hydra'
    lightning_service = 'nova-lightning'
    ecs_cluster = 'default' # Update this with your cluster name
    on_demand_scaling(hydra_asg, lightning_service, ecs_cluster)

if __name__ == "__main__":
    run_scale_handler()
