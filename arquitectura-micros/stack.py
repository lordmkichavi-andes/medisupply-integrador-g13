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
from services.offer_manager_service import OfferManagerService
from services.orders_service import OrdersService
from services.products_service import ProductsService
from services.reports_service import ReportsService
from services.routes_service import RoutesService
from services.users_service import UsersService


class MediSupplyStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, experiment_config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.experiment_config = experiment_config

        # Crear infraestructura base
        self._create_infrastructure()

        # Crear servicios p
        self._create_services()

        # Configurar api
        self._configure_api()

    def _create_infrastructure(self):
        """Crear infraestructura base necesaria"""

        # VPC
        self.vpc = ec2.Vpc(
            self, "MediSupplyVpc",
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
            self, "MediSupplyCluster",
            vpc=self.vpc,
            cluster_name="medi-supply-cluster"
        )

        # Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self, "MediSupplyALB",
            vpc=self.vpc,
            internet_facing=True
        )

        # Listener del ALB
        self.alb_listener = self.alb.add_listener(
            "MediSupplyALBListener",
            port=80,
            open=True,
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=404,
                message_body="Not Found"
            )
        )

        # RDS Database
        self.core_database = rds.DatabaseInstance(
            self, "MediSupplyCoreDB",
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

        self.transactional_database = rds.DatabaseInstance(
            self, "MediSupplyTransactionalDB",
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
            self, "RedisSecurityGroup",
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
            self, "MediSupplyCache",
            cache_node_type="cache.t3.micro",
            num_cache_nodes=1,
            engine="redis",
            vpc_security_group_ids=[cache_security_group.security_group_id],
            cache_subnet_group_name=cache_subnet_group.ref
        )
        # API Gateway
        self.api = apigateway.RestApi(
            self, "MediSupplyAPI",
            rest_api_name="MediSupply API",
            description="API para experimentos de confidencialidad y latencia"
        )

        # Cognito User Pool (mínimo necesario para integrar con authorizer)
        self.user_pool = cognito.UserPool(
            self, "MediSupplyUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True)
        )

        # User Pool Client
        self.user_pool_client = cognito.UserPoolClient(
            self, "MediSupplyUserPoolClient",
            user_pool=self.user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True,
                user_srp=True
            )
        )

        # Cognito User Pool Groups (para autorizaciones por rol)
        self.admin_group = cognito.CfnUserPoolGroup(
            self, "AdminGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="admin",
            description="Administradores con acceso completo",
            precedence=1
        )

        self.compras_group = cognito.CfnUserPoolGroup(
            self, "ComprasGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="compras",
            description="Equipo de compras y proveedores",
            precedence=10
        )

        self.logistica_group = cognito.CfnUserPoolGroup(
            self, "LogisticaGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="logistica",
            description="Equipo de logística e inventarios",
            precedence=20
        )

        self.ventas_group = cognito.CfnUserPoolGroup(
            self, "VentasGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="ventas",
            description="Fuerza de ventas y comerciales",
            precedence=30
        )

        # Lambda Autorizadora
        self.authorizer_lambda = lambda_.Function(
            self, "MediSupplySecurityAuthorizer",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="authorizer.lambda_handler",
            code=lambda_.Code.from_asset("lambda"),
            timeout=Duration.seconds(30)
        )

        # API Gateway Token Authorizer usando la Lambda
        self.cognito_authorizer = apigateway.TokenAuthorizer(
            self, "MediSupplyLambdaAuthorizer",
            handler=self.authorizer_lambda,
            authorizer_name="MediSupply-Security-Authorizer"
        )


    def _create_services(self):
        """Crear servicios necesarios para MediSupplys"""
        if self.experiment_config.get('offer-manager', {}).get('enabled', False):
            self.products_service = OfferManagerService(
                self, "OfferManagerService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
        if self.experiment_config.get('orders', {}).get('enabled', False):
            self.products_service = OrdersService(
                self, "OrdersService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
        if self.experiment_config.get('products', {}).get('enabled', False):
            self.products_service = ProductsService(
                self, "ProductsService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.core_database,
                cache=self.cache,
                alb_listener=self.alb_listener
            )
        if self.experiment_config.get('reports', {}).get('enabled', False):
            self.products_service = ReportsService(
                self, "ReportsService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database_database,
                alb_listener=self.alb_listener
            )
        if self.experiment_config.get('routes', {}).get('enabled', False):
            self.products_service = RoutesService(
                self, "RoutesService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
        if self.experiment_config.get('users', {}).get('enabled', False):
            self.products_service = UsersService(
                self, "UsersService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.core_database,
                alb_listener=self.alb_listener
            )

    def _configure_api(self):
        if  self.experiment_config.get('offer-manager', {}).get('enabled', False):
            self._configure_offer_manager()
        if  self.experiment_config.get('orders', {}).get('enabled', False):
            self._configure_orders()
        if  self.experiment_config.get('products', {}).get('enabled', False):
            self._configure_products()
        if  self.experiment_config.get('reports', {}).get('enabled', False):
            self._configure_reports()
        if  self.experiment_config.get('routes', {}).get('enabled', False):
            self._configure_routes()
        if  self.experiment_config.get('users', {}).get('enabled', False):
            self._configure_users()


    def _configure_offer_manager(self):
        # Endpoint para Offer Manager Service
        offer_manager_resource = self.api.root.add_resource("offers")

    def _configure_orders(self):
        # Endpoint para Offer Manager Service
        orders_resource = self.api.root.add_resource("orders")

    def _configure_products(self):
        """Configurar experimento de latencia"""

        # Endpoint para Products Service
        products_resource = self.api.root.add_resource("products")
        products_resource.add_method(
            "GET",
            apigateway.HttpIntegration(
                f"http://{self.alb.load_balancer_dns_name}/products/available",
                http_method="GET"
            ),
            authorizer=self.cognito_authorizer
        )

    def _configure_reports(self):
        # Endpoint para Offer Manager Service
        reports_resource = self.api.root.add_resource("reports")

    def _configure_routes(self):
        # Endpoint para Offer Manager Service
        routes_resource = self.api.root.add_resource("routes")

    def _configure_users(self):
        # Endpoint para Offer Manager Service
        users_resource = self.api.root.add_resource("users")