"""RosterFit on AWS (CDK, Python).

Resources
---------
* S3 bucket          data lake (partitioned Parquet marts), model artifacts, Athena results
* Glue database      catalog for the lake tables (DDL from `rosterfit athena-ddl`)
* Athena workgroup   serverless SQL over the lake, with a per-query scan limit as a cost guard
* ECR image          built from the repo Dockerfile
* ECS Fargate task   nightly refresh on an EventBridge schedule: ingest -> SQL marts -> retrain
                     -> publish marts + artifacts to S3
* Fargate service    (optional, `-c deploy_app=true`) the Streamlit dashboard behind an ALB
* IAM                least-privilege access to the bucket and Bedrock (Claude scouting reports)

The VPC has public subnets only and no NAT gateway, to keep idle cost near zero.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_applicationautoscaling as appscaling
from aws_cdk import aws_athena as athena
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[1]
BEDROCK_MODEL = "anthropic.claude-opus-5-5"


class RosterFitStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, deploy_app: bool = False, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self, "Lake",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(prefix="athena-results/", expiration=Duration.days(7)),
                s3.LifecycleRule(noncurrent_version_expiration=Duration.days(30)),
            ],
        )

        glue.CfnDatabase(self, "GlueDb", catalog_id=self.account,
                         database_input=glue.CfnDatabase.DatabaseInputProperty(
                             name="rosterfit", description="RosterFit NBA lineup and prospect marts"))

        workgroup = athena.CfnWorkGroup(
            self, "Workgroup", name="rosterfit",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                bytes_scanned_cutoff_per_query=1_000_000_000,  # 1 GB guardrail
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{bucket.bucket_name}/athena-results/"),
            ),
        )

        image = ecs.ContainerImage.from_docker_image_asset(ecr_assets.DockerImageAsset(
            self, "Image", directory=str(REPO_ROOT), platform=ecr_assets.Platform.LINUX_AMD64,
            exclude=[".venv", ".git", "data", "infra/cdk.out", "notebooks", "tests"]))

        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0,
                      subnet_configuration=[ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC)])
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.ENABLED)

        env = {"ROSTERFIT_S3_BUCKET": bucket.bucket_name, "ROSTERFIT_LLM_PROVIDER": "bedrock",
               "ROSTERFIT_BEDROCK_MODEL": BEDROCK_MODEL, "AWS_REGION": self.region}

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:CreateInference",
                     "bedrock-mantle:*"],
            resources=["*"],  # Bedrock model / inference-profile ARNs vary by region; scope down per account.
        )

        # Nightly refresh: 10:00 UTC (early morning US time, after last night's box scores land).
        refresh = ecs_patterns.ScheduledFargateTask(
            self, "NightlyRefresh", cluster=cluster,
            schedule=appscaling.Schedule.cron(minute="0", hour="10"),
            subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            scheduled_fargate_task_image_options=ecs_patterns.ScheduledFargateTaskImageOptions(
                image=image, command=["refresh"], cpu=2048, memory_limit_mib=8192, environment=env,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="refresh", log_retention=logs.RetentionDays.ONE_MONTH),
            ),
        )
        # Public subnet without NAT: the task needs a public IP to reach the data sources.
        cfn_rule = refresh.event_rule.node.default_child
        cfn_rule.add_property_override("Targets.0.EcsParameters.NetworkConfiguration.AwsVpcConfiguration.AssignPublicIp",
                                       "ENABLED")
        bucket.grant_read_write(refresh.task_definition.task_role)
        refresh.task_definition.task_role.add_to_principal_policy(bedrock_policy)

        if deploy_app:
            app = ecs_patterns.ApplicationLoadBalancedFargateService(
                self, "Dashboard", cluster=cluster, cpu=1024, memory_limit_mib=4096, desired_count=1,
                assign_public_ip=True, public_load_balancer=True,
                task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                    image=image, container_port=8501, command=["app"], environment=env,
                    log_driver=ecs.LogDrivers.aws_logs(stream_prefix="app",
                                                       log_retention=logs.RetentionDays.ONE_MONTH)),
            )
            app.target_group.configure_health_check(path="/_stcore/health", healthy_http_codes="200")
            bucket.grant_read(app.task_definition.task_role)
            app.task_definition.task_role.add_to_principal_policy(bedrock_policy)
            CfnOutput(self, "DashboardUrl", value=f"http://{app.load_balancer.load_balancer_dns_name}")

        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "AthenaWorkgroup", value=workgroup.name)
