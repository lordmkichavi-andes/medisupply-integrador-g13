from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    Duration
)
import os
from constructs import Construct
account=os.getenv('CDK_DEFAULT_ACCOUNT', '868422696635')
region=os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
image = f"{account}.dkr.ecr.{region}.amazonaws.com/products"
class ProductsService(Construct):
    """Servicio de productos para experimento de latencia"""

    def __init__(self, scope: Construct, construct_id: str,
                 cluster: ecs.Cluster, vpc: ec2.Vpc,
                 database: rds.DatabaseInstance, cache: elasticache.CfnReplicationGroup,  # ✅ Cambio aquí
                 alb_listener: elbv2.ApplicationListener, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.cluster = cluster
        self.vpc = vpc
        self.database = database
        self.cache = cache
        self.alb_listener = alb_listener

        # Crear task definition
        self.task_definition = self._create_task_definition()

        # Crear target group
        self.target_group = self._create_target_group()

        # Crear servicio
        self.service = self._create_service()

        # Configurar todas las conexiones del servicio
        self._configure_service_connections()

        # Configurar ALB
        self._configure_alb()

    def _create_task_definition(self):
        """Crear definición de tarea para Products Service"""
        task_role = iam.Role(
            self, "ProductsServiceTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        log_group = logs.LogGroup(
            self, "ProductsServiceLogGroup",
            log_group_name="/ecs/products-service",
            retention=logs.RetentionDays.ONE_WEEK
        )

        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            resources=["*"]  # ECR actions often require resource: *
        ))

        task_definition = ecs.FargateTaskDefinition(
            self, "ProductsServiceTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            execution_role=task_role,
            task_role=task_role
        )
        db_password_secret = ecs.Secret.from_secrets_manager(
            self.database.secret,
            "password"
        )
        image_uri_clean = str(image).strip()
        print(image_uri_clean)
        container = task_definition.add_container(
            "ProductsServiceContainer",
            image=ecs.ContainerImage.from_registry(
                image_uri_clean
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="products-service",
                log_group=log_group
            ),
            environment={
                "SERVICE_NAME": "products-service",
                "LOG_LEVEL": "INFO",
                "DB_HOST": self.database.instance_endpoint.hostname,
                "DB_PORT": "5432",
                "CACHE_HOST": self.cache.attr_redis_endpoint_address,
                "CACHE_PORT": self.cache.attr_redis_endpoint_port,
                "CACHE_DB": "0",
                "DB_NAME": "productosdb",
                "DB_USER": "postgres",
            },
            secrets={
                "DB_PASSWORD": db_password_secret
            },
            port_mappings=[
                ecs.PortMapping(
                    container_port=8080,
                    protocol=ecs.Protocol.TCP
                )
            ]
        )
        self.database.secret.grant_read(task_definition.task_role)
        return task_definition

    def _create_service(self):
        """Crear servicio ECS para Products Service"""
        service = ecs.FargateService(
            self, "ProductsService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=1,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            health_check_grace_period=Duration.seconds(60)
        )
        return service

    def _create_target_group(self):
        """Crear target group para el ALB"""
        target_group = elbv2.ApplicationTargetGroup(
            self, "ProductsServiceTargetGroup",
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            vpc=self.vpc,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/health",
                protocol=elbv2.Protocol.HTTP,
                port="8080"
            )
        )
        return target_group

    def _configure_service_connections(self):
        """
        Configura las reglas de seguridad para el servicio Fargate y la conexión con Redis.
        """
        alb_security_group = self.alb_listener.load_balancer.connections.security_groups[0]
        service_security_group = self.service.connections.security_groups[0]

        service_security_group.add_ingress_rule(
            peer=alb_security_group,
            connection=ec2.Port.tcp(8080),
            description="Allow inbound traffic from ALB"
        )

        self.database.connections.allow_default_port_from(
            service_security_group,
            description="Allow ProductsService Fargate to connect to PostgreSQL RDS"
        )

        cache_security_group_id = self.cache.vpc_security_group_ids[0]
        redis_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "RedisSecurityGroup",
            security_group_id=cache_security_group_id
        )

        redis_security_group.add_ingress_rule(
            peer=service_security_group,
            connection=ec2.Port.tcp(6379),
            description="Allow Fargate service to connect to Redis"
        )

    def _configure_alb(self):
        """Configurar ALB para el servicio"""
        self.alb_listener.add_target_groups(
            "ProductsServiceTargetGroup",
            target_groups=[self.target_group],
            conditions=[elbv2.ListenerCondition.path_patterns(["/products*"])],
            priority=200
        )
        self.service.attach_to_application_target_group(self.target_group)