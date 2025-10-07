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
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    Duration,
    RemovalPolicy,
    CfnOutput
)
import os
from constructs import Construct
from services.offer_manager_service import OfferManagerService
from services.orders_service import OrdersService
from services.products_service import ProductsService
from services.reports_service import ReportsService
from services.routes_service import RoutesService
from services.users_service import UsersService


class MediSupplyStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')

        # Crear infraestructura base
        self._create_infrastructure()

        # Crear servicios p
        self._create_services()

        # Configurar api
        self._configure_api()
        
        # Configurar CORS universal (una sola vez)
        self._enable_universal_cors()
        
        # Crear frontend
        self._create_frontend()

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

        # RDS Databases
        # Security Group para RDS (puerto 5432 abierto)
        self.rds_core_security_group = ec2.SecurityGroup(
            self, "RDSCoreSecurityGroup",
            vpc=self.vpc,
            description="Security group for public RDS access",
            allow_all_outbound=True
        )

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
            security_groups=[self.rds_core_security_group],
            allocated_storage=20,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            delete_automated_backups=True,
            credentials=rds.Credentials.from_generated_secret("postgres")
        )

        self.rds_transacitional_security_group = ec2.SecurityGroup(
            self, "RDSTransactionalSecurityGroup",
            vpc=self.vpc,
            description="Security group for public RDS access",
            allow_all_outbound=True
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
            security_groups=[self.rds_transacitional_security_group],
            allocated_storage=20,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            delete_automated_backups=True,
            credentials=rds.Credentials.from_generated_secret("postgres")
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

        # API Gateway Request Authorizer usando la Lambda (permite acceso a headers)
        self.cognito_authorizer = apigateway.RequestAuthorizer(
            self, "MediSupplyLambdaAuthorizer",
            handler=self.authorizer_lambda,
            authorizer_name="MediSupply-Security-Authorizer",
            identity_sources=[apigateway.IdentitySource.header("Authorization")]
        )


    def _create_services(self):
        """Crear servicios necesarios para MediSupplys"""
        if self.config.get('offer-manager', {}).get('enabled', False):
            self.offers_service = OfferManagerService(
                self, "OfferManagerService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
            offers_fargate_sg = self.offers_service.service.connections.security_groups[0]

            self.transactional_database.connections.allow_default_port_from(
                offers_fargate_sg,
                description="Allow OfferManagerService Fargate to connect to PostgreSQL"
            )
        if self.config.get('orders', {}).get('enabled', False):
            self.orders_service = OrdersService(
                self, "OrdersService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
            orders_fargate_sg = self.orders_service.service.connections.security_groups[0]

            self.transactional_database.connections.allow_default_port_from(
                orders_fargate_sg,
                description="Allow OrdersService Fargate to connect to PostgreSQL"
            )
        if self.config.get('products', {}).get('enabled', False):
            self.products_service = ProductsService(
                self, "ProductsService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.core_database,
                cache=self.cache,
                alb_listener=self.alb_listener
            )
            products_fargate_sg = self.products_service.service.connections.security_groups[0]

            self.core_database.connections.allow_default_port_from(
                products_fargate_sg,
                description="Allow ProductsService Fargate to connect to PostgreSQL"
            )
        if self.config.get('reports', {}).get('enabled', False):
            self.reports_service = ReportsService(
                self, "ReportsService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database_database,
                alb_listener=self.alb_listener
            )
            reports_fargate_sg = self.reports_service.service.connections.security_groups[0]

            self.transactional_database.connections.allow_default_port_from(
                reports_fargate_sg,
                description="Allow ReportsService Fargate to connect to PostgreSQL"
            )
        if self.config.get('routes', {}).get('enabled', False):
            self.routes_service = RoutesService(
                self, "RoutesService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.transactional_database,
                alb_listener=self.alb_listener
            )
            routes_fargate_sg = self.routes_service.service.connections.security_groups[0]

            self.transactional_database.connections.allow_default_port_from(
                routes_fargate_sg,
                description="Allow RoutesService Fargate to connect to PostgreSQL"
            )
        if self.config.get('users', {}).get('enabled', False):
            self.users_service = UsersService(
                self, "UsersService",
                cluster=self.ecs_cluster,
                vpc=self.vpc,
                database=self.core_database,
                alb_listener=self.alb_listener
            )
            users_fargate_sg = self.users_service.service.connections.security_groups[0]

            self.core_database.connections.allow_default_port_from(
                users_fargate_sg,
                description="Allow UsersService Fargate to connect to PostgreSQL"
            )

    def _configure_api(self):
        if  self.config.get('offer-manager', {}).get('enabled', False):
            self._configure_offer_manager()
        if  self.config.get('orders', {}).get('enabled', False):
            self._configure_orders()
        if  self.config.get('products', {}).get('enabled', False):
            self._configure_products()
        if  self.config.get('reports', {}).get('enabled', False):
            self._configure_reports()
        if  self.config.get('routes', {}).get('enabled', False):
            self._configure_routes()
        if  self.config.get('users', {}).get('enabled', False):
            self._configure_users()


    def _configure_offer_manager(self):
        """Configurar endpoint de ofertas"""
        # Endpoint para Offer Manager Service
        offer_manager_resource = self.api.root.add_resource("offers")
        
        # Configurar métodos HTTP simples (CORS se maneja universalmente)
        offer_manager_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/offers"), authorizer=self.cognito_authorizer)
        offer_manager_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/offers", http_method="POST"), authorizer=self.cognito_authorizer)
        offer_manager_resource.add_method("PUT", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/offers", http_method="PUT"), authorizer=self.cognito_authorizer)
        offer_manager_resource.add_method("DELETE", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/offers", http_method="DELETE"), authorizer=self.cognito_authorizer)

    def _configure_orders(self):
        """Configurar endpoint de órdenes"""
        # Endpoint para Orders Service
        orders_resource = self.api.root.add_resource("orders")
        
        # Configurar métodos HTTP simples (CORS se maneja universalmente)
        orders_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/orders"), authorizer=self.cognito_authorizer)
        orders_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/orders", http_method="POST"), authorizer=self.cognito_authorizer)
        orders_resource.add_method("PUT", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/orders", http_method="PUT"), authorizer=self.cognito_authorizer)
        orders_resource.add_method("DELETE", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/orders", http_method="DELETE"), authorizer=self.cognito_authorizer)

    def _configure_products(self):
        """Configurar experimento de latencia"""

        # Endpoint para Products Service
        products_resource = self.api.root.add_resource("products")
        
        # Configurar métodos HTTP simples (CORS se configurará después del despliegue)
        products_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/products/available"), authorizer=self.cognito_authorizer)
        
        # Otros métodos simples
        products_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/products/available", http_method="POST"), authorizer=self.cognito_authorizer)
        products_resource.add_method("PUT", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/products/available", http_method="PUT"), authorizer=self.cognito_authorizer)
        products_resource.add_method("DELETE", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/products/available", http_method="DELETE"), authorizer=self.cognito_authorizer)

    def _configure_reports(self):
        """Configurar endpoint de reportes"""
        # Endpoint para Reports Service
        reports_resource = self.api.root.add_resource("reports")
        
        # Configurar métodos HTTP simples (CORS se maneja universalmente)
        reports_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/reports"), authorizer=self.cognito_authorizer)
        reports_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/reports", http_method="POST"), authorizer=self.cognito_authorizer)


    def _enable_universal_cors(self):
        """
        Configuración CORS universal - una sola vez para todo el API Gateway
        Más simple, flexible y sin redundancia
        """
        
        # Configurar CORS en el recurso raíz - se aplica a TODOS los recursos automáticamente
        self.api.root.add_cors_preflight(
            allow_origins=["*"],  # Cualquier origen (localhost, CloudFront, etc.)
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
            allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token", "X-Requested-With", "Accept", "Origin"],
            allow_credentials=False,
            max_age=Duration.days(1)  # Cache por 24 horas
        )
        
        # Configurar CORS para respuestas de error también
        self._configure_cors_for_all_resources()

    def _configure_cors_for_all_resources(self):
        """
        Configura CORS para todas las respuestas (incluyendo errores)
        """
        # Configurar CORS para el recurso raíz
        self._add_cors_to_resource(self.api.root)

        # Configurar CORS para todos los recursos existentes
        for resource in [self.api.root.get_resource("products"),
                        self.api.root.get_resource("users"),
                        self.api.root.get_resource("reports"),
                        self.api.root.get_resource("routes")]:
            if resource:
                self._add_cors_to_resource(resource)

    def _add_cors_to_resource(self, resource):
        """
        Agrega headers CORS a un recurso específico
        """
        # Configurar MethodResponse con headers CORS
        for method in ["GET", "POST", "PUT", "DELETE"]:
            try:
                method_obj = resource.get_method(method)
                if method_obj:
                    # Agregar headers CORS a MethodResponse
                    method_obj.add_method_response(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": True,
                            "method.response.header.Access-Control-Allow-Headers": True,
                            "method.response.header.Access-Control-Allow-Methods": True
                        }
                    )
                    
                    # Agregar headers CORS a IntegrationResponse
                    integration = method_obj.integration
                    if integration:
                        integration.add_integration_response(
                            status_code="200",
                            response_parameters={
                                "method.response.header.Access-Control-Allow-Origin": "'*'",
                                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",
                                "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'"
                            }
                        )
            except Exception as e:
                # Ignorar errores si el método no existe
                pass

    def _configure_routes(self):
        """Configurar endpoint de rutas"""
        # Endpoint para Routes Service
        routes_resource = self.api.root.add_resource("routes")
        
        # Configurar métodos HTTP simples (CORS se maneja universalmente)
        routes_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/routes"), authorizer=self.cognito_authorizer)
        routes_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/routes", http_method="POST"), authorizer=self.cognito_authorizer)
        routes_resource.add_method("PUT", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/routes", http_method="PUT"), authorizer=self.cognito_authorizer)

    def _configure_users(self):
        """Configurar endpoint de usuarios"""
        # Endpoint para Users Service
        users_resource = self.api.root.add_resource("users")
        
        # Configurar métodos HTTP simples (CORS se maneja universalmente)
        users_resource.add_method("GET", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/users"), authorizer=self.cognito_authorizer)
        users_resource.add_method("POST", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/users", http_method="POST"), authorizer=self.cognito_authorizer)
        users_resource.add_method("PUT", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/users", http_method="PUT"), authorizer=self.cognito_authorizer)
        users_resource.add_method("DELETE", apigateway.HttpIntegration(f"http://{self.alb.load_balancer_dns_name}/users", http_method="DELETE"), authorizer=self.cognito_authorizer)

    def _create_frontend(self):
        """Usar S3 existente para el frontend y configurar CloudFront"""
        EXISTING_BUCKET_NAME = "medisupply-frontend-123456"

        self.frontend_bucket = s3.Bucket.from_bucket_attributes(
            self, "MediSupplyExistingFrontendBucket",
            bucket_arn=f"arn:aws:s3:::{EXISTING_BUCKET_NAME}-{self.region}",
        )

        oai = cloudfront.OriginAccessIdentity(
            self, "OAI",
            comment=f"OAI para acceder a {EXISTING_BUCKET_NAME}"
        )

        bucket_policy = s3.BucketPolicy(
            self, "FrontendBucketPolicy",
            bucket=self.frontend_bucket,
            # Mantener la política al eliminar el stack para evitar errores
            removal_policy=RemovalPolicy.RETAIN
        )

        oai_read_statement = iam.PolicyStatement(
            sid="GrantAccessToCloudFrontOAI",
            effect=iam.Effect.ALLOW,
            # Usar el principal de concesión del OAI
            principals=[oai.grant_principal],
            actions=["s3:GetObject"],
            resources=[self.frontend_bucket.arn_for_objects("*")]
        )

        bucket_policy.document.add_statements(oai_read_statement)

        cors_policy = cloudfront.ResponseHeadersPolicy.CORS_ALLOW_ALL_ORIGINS
        # CloudFront Distribution para el frontend
        self.frontend_distribution = cloudfront.Distribution(
            self, "MediSupplyFrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    bucket=self.frontend_bucket,
                    origin_access_identity=oai,
                    origin_path="/"
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=cors_policy,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                compress=True
            ),
            default_root_object="src/index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html"
                )
            ]
        )

        # CORS ya configurado universalmente en _enable_universal_cors()

        # -------------------------------------------------------------------------

        # Outputs
        CfnOutput(
            self, "FrontendURL",
            value=f"https://{self.frontend_distribution.distribution_domain_name}",
            description="URL del frontend"
        )
        CfnOutput(
            self, "FrontendDistributionId",
            value=self.frontend_distribution.distribution_id,  # <-- Propiedad a usar
            description="ID de la Distribución de CloudFront"
        )
