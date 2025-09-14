from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
    RemovalPolicy
)
from constructs import Construct
from services.products_service import ProductsService


class ExperimentoStack(Stack):
    """Stack principal para los experimentos de confidencialidad y latencia"""

    def __init__(self, scope: Construct, construct_id: str, experiment_config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.experiment_config = experiment_config

        # Crear infraestructura base
        self._create_infrastructure()

        # Crear servicios para experimentos
        self._create_services()

        # Configurar experimentos
        self._configure_experiments()

    def _create_infrastructure(self):
        """Crear infraestructura base necesaria para los experimentos"""

        # VPC
        self.vpc = ec2.Vpc(
            self, "ExperimentoVpc",
            cidr="10.0.0.0/16",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # ECS Cluster
        self.ecs_cluster = ecs.Cluster(
            self, "ExperimentoCluster",
            vpc=self.vpc,
            cluster_name="experimento-cluster"
        )

        # Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self, "ExperimentoALB",
            vpc=self.vpc,
            internet_facing=True
        )

        # Listener del ALB
        self.alb_listener = self.alb.add_listener(
            "ExperimentoALBListener",
            port=80,
            open=True,
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=404,
                message_body="Not Found"
            )
        )

        # RDS Database
        self.database = rds.DatabaseInstance(
            self, "ExperimentoDB",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_7
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            allocated_storage=20,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            delete_automated_backups=True
        )

        # ElastiCache Redis Security Group
        cache_security_group = ec2.SecurityGroup(
            self, "CacheSecurityGroup",
            vpc=self.vpc,
            description="Security group for Redis cache",
            allow_all_outbound=True
        )

        # ElastiCache Subnet Group
        cache_subnet_group = elasticache.CfnSubnetGroup(
            self, "CacheSubnetGroup",
            description="Subnet group for Redis cache",
            subnet_ids=[subnet.subnet_id for subnet in self.vpc.private_subnets]
        )

        # ElastiCache Redis
        self.cache = elasticache.CfnCacheCluster(
            self, "ExperimentoCache",
            cache_node_type="cache.t3.micro",
            num_cache_nodes=1,
            engine="redis",
            vpc_security_group_ids=[cache_security_group.security_group_id],
            cache_subnet_group_name=cache_subnet_group.ref
        )
        # API Gateway
        self.api = apigateway.RestApi(
            self, "ExperimentoAPI",
            rest_api_name="Experimento API",
            description="API para experimentos de confidencialidad y latencia"
        )


    def _create_services(self):
        """Crear servicios necesarios para los experimentos"""


        # Products Service (para experimento de latencia)
        if self.experiment_config.get('latency', {}).get('enabled', False):
            self.products_service = ProductsService(
                self, "ProductsService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.database,
                cache=self.cache,
                alb_listener=self.alb_listener
            )

    def _configure_experiments(self):
        """Configurar experimentos específicos"""

        # Configurar experimento de latencia
        if self.experiment_config.get('latency', {}).get('enabled', False):
            self._configure_latency_experiment()

    def _configure_confidentiality_experiment(self):
        """Configurar experimento de confidencialidad"""


    def _configure_latency_experiment(self):
        """Configurar experimento de latencia"""

        # Endpoint para Products Service
        products_resource = self.api.root.add_resource("products")
        products_resource.add_method(
            "GET",
            apigateway.HttpIntegration(
                f"http://{self.alb.load_balancer_dns_name}/products/available",
                http_method="GET"
            ),
        )