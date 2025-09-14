from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_rds as rds,
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

class ExperimentoStackV5(Stack):
    def __init__(self, scope: Construct, construct_id: str, experiment_config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.experiment_config = experiment_config
        self._create_infrastructure()

    def _create_infrastructure(self):
        """Crear infraestructura completa V5: RDS + Lambda + Fargate + Cognito"""
        
        # VPC por defecto (más simple que crear una nueva)
        self.default_vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)
        
        # Security Group para RDS (puerto 5432 abierto)
        self.rds_security_group = ec2.SecurityGroup(
            self, "RDSSecurityGroup",
            vpc=self.default_vpc,
            description="Security group for public RDS access",
            allow_all_outbound=True
        )
        
        # Permitir acceso PostgreSQL desde cualquier IP (para experimentos)
        self.rds_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL access from anywhere"
        )
        
        # RDS Database (PÚBLICO - una sola base de datos para todo)
        self.database = rds.DatabaseInstance(
            self, "ExperimentoDB",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_7
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO
            ),
            vpc=self.default_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            security_groups=[self.rds_security_group],
            allocated_storage=20,
            publicly_accessible=True,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            delete_automated_backups=True,
            credentials=rds.Credentials.from_generated_secret("postgres")
        )
        
        # Cognito User Pool con atributos personalizados para MeddySupply
        self.user_pool = cognito.UserPool(
            self, "ExperimentoUserPool",
            user_pool_name="experimento-user-pool-v5",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            # Atributos personalizados para MeddySupply
            custom_attributes={
                'region': cognito.StringAttribute(min_len=1, max_len=20, mutable=True),
                'country_code': cognito.StringAttribute(min_len=2, max_len=3, mutable=True),
                'timezone': cognito.StringAttribute(min_len=1, max_len=50, mutable=True),
                'role': cognito.StringAttribute(min_len=1, max_len=30, mutable=True),
                'department': cognito.StringAttribute(min_len=1, max_len=50, mutable=True),
                'employee_id': cognito.StringAttribute(min_len=1, max_len=20, mutable=True),
                'location_code': cognito.StringAttribute(min_len=1, max_len=10, mutable=True),
                'business_start': cognito.StringAttribute(min_len=1, max_len=10, mutable=True),
                'business_end': cognito.StringAttribute(min_len=1, max_len=10, mutable=True),
                'authorized_countries': cognito.StringAttribute(min_len=1, max_len=100, mutable=True),
                'risk_tolerance': cognito.StringAttribute(min_len=1, max_len=20, mutable=True)
            },
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Cognito User Pool Client
        self.user_pool_client = cognito.UserPoolClient(
            self, "ExperimentoUserPoolClient",
            user_pool=self.user_pool,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                admin_user_password=True  # Habilitamos ADMIN_NO_SRP_AUTH
            )
        )
        
        # Lambda Autorizador MeddySupply con Cognito REAL
        self.authorizer_lambda = lambda_.Function(
            self, "MediSupplyAuthorizerReal",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="lambda_authorizer_cognito_real.lambda_handler",  # ✅ COGNITO REAL con CACHE
            code=lambda_.Code.from_asset("lambda_code"),
            timeout=Duration.seconds(15),  # Más tiempo para consultas a Cognito
            memory_size=512,  # Más memoria para JWT processing
            environment={
                'USER_POOL_ID': self.user_pool.user_pool_id,
                'USER_POOL_CLIENT_ID': self.user_pool_client.user_pool_client_id
                # AWS_REGION ya está disponible automáticamente en Lambda
            }
        )
        
        # Permisos para MeddySupply Real - necesita acceso a Cognito
        self.authorizer_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    'cognito-idp:AdminGetUser',
                    'cognito-idp:ListUsers',
                    'cognito-idp:AdminListGroupsForUser'
                ],
                resources=[self.user_pool.user_pool_arn]
            )
        )
        
        # API Gateway con autorizador
        self.api = apigateway.RestApi(
            self, "ExperimentoAPI",
            rest_api_name="Experimento API V5",
            description="API completa para experimentos - Lambda + Fargate + RDS + Cognito"
        )
        
        # Lambda Autorizador para API Gateway
        self.api_authorizer = apigateway.TokenAuthorizer(
            self, "ExperimentoAPIAuthorizer",
            handler=self.authorizer_lambda,
            identity_source=apigateway.IdentitySource.header("Authorization")
        )
        
        # Lambda mejorado para endpoints de MeddySupply Demo
        self.test_lambda = lambda_.Function(
            self, "MediSupplyEndpointLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_inline("""
import json
from datetime import datetime

def lambda_handler(event, context):
    # Extraer información del autorizador
    authorizer_context = event.get('requestContext', {}).get('authorizer', {})
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    # Información del usuario desde el autorizador MeddySupply
    user_info = {
        'username': authorizer_context.get('username', 'unknown'),
        'region': authorizer_context.get('region', 'unknown'),
        'role': authorizer_context.get('role', 'unknown'),
        'risk_score': authorizer_context.get('risk_score', '0.0'),
        'response_time_ms': authorizer_context.get('response_time_ms', '0'),
        'auth_status': authorizer_context.get('auth_status', 'unknown')
    }
    
    # Respuesta específica según el endpoint
    if '/admin/' in path:
        message = 'Panel de Administración MeddySupply'
        data = {
            'dashboard': 'admin_dashboard',
            'permissions': ['read', 'write', 'admin'],
            'alerts': ['security_check_passed']
        }
    elif '/secure/' in path:
        message = 'Datos Seguros MeddySupply'
        data = {
            'medical_data': ['patient_records', 'prescriptions'],
            'access_level': 'confidential',
            'compliance': ['HIPAA', 'FDA']
        }
    else:
        message = 'Endpoint de Prueba MeddySupply'
        data = {
            'service': 'medisupply_api',
            'version': 'demo',
            'features': ['regional_auth', 'risk_scoring']
        }
    
    response = {
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'user_info': user_info,
        'endpoint': path,
        'method': method,
        'medisupply_data': data,
        'authorization': {
            'provider': 'medisupply_lambda_authorizer',
            'risk_assessment': 'completed',
            'regional_compliance': 'verified'
        }
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'X-MediSupply-Service': 'demo-api'
        },
        'body': json.dumps(response, indent=2)
    }
            """),
            timeout=Duration.seconds(10)
        )

        # Endpoints para MeddySupply Demo
        # /test - Endpoint básico de prueba
        test_resource = self.api.root.add_resource("test")
        test_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                self.test_lambda,
                proxy=True
            ),
            authorizer=self.api_authorizer
        )
        
        # /secure/data - Endpoint para datos seguros
        secure_resource = self.api.root.add_resource("secure")
        data_resource = secure_resource.add_resource("data")
        data_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                self.test_lambda,
                proxy=True
            ),
            authorizer=self.api_authorizer
        )
        
        # /admin/dashboard - Endpoint para administradores
        admin_resource = self.api.root.add_resource("admin")
        dashboard_resource = admin_resource.add_resource("dashboard")
        dashboard_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                self.test_lambda,
                proxy=True
            ),
            authorizer=self.api_authorizer
        )
        
        # ECS Cluster (en VPC por defecto)
        self.ecs_cluster = ecs.Cluster(
            self, "ExperimentoCluster",
            vpc=self.default_vpc,
            cluster_name="experimento-cluster-v5"
        )
        
        # Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self, "ExperimentoALB",
            vpc=self.default_vpc,
            internet_facing=True
        )
        
        # ALB Listener
        self.alb_listener = self.alb.add_listener(
            "ExperimentoALBListener",
            port=80,
            open=True,
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=404,
                message_body="ALB V5 - Not Found"
            )
        )
        
        # Crear servicios Fargate
        self._create_fargate_services()
        
        # Outputs importantes
        from aws_cdk import CfnOutput
        
        CfnOutput(
            self, "DatabaseEndpoint",
            value=self.database.instance_endpoint.hostname,
            description="RDS Database Endpoint (público)"
        )
        
        CfnOutput(
            self, "APIGatewayURL",
            value=self.api.url,
            description="API Gateway URL"
        )
        
        CfnOutput(
            self, "ALBURL",
            value=f"http://{self.alb.load_balancer_dns_name}",
            description="Application Load Balancer URL"
        )
        
        CfnOutput(
            self, "UserPoolID",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )
        
        CfnOutput(
            self, "UserPoolClientID",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )

    def _create_fargate_services(self):
        """Crear servicios Fargate que usan RDS"""
        
        # Security Group para ECS
        ecs_security_group = ec2.SecurityGroup(
            self, "ECSSecurityGroup",
            vpc=self.default_vpc,
            description="Security group for ECS services",
            allow_all_outbound=False  # Configuración manual
        )
        
        # Permitir tráfico HTTP desde ALB
        ecs_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8080),
            description="HTTP from internet"
        )
        
        # Permitir acceso saliente a RDS
        ecs_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL access to RDS"
        )
        
        # Permitir acceso saliente a internet (para descargas)
        ecs_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS to internet"
        )
        
        ecs_security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="HTTP to internet"
        )
        
        # Products Service
        self._create_products_service(ecs_security_group)
        
        # Auth Service  
        self._create_auth_service(ecs_security_group)

    def _create_products_service(self, security_group):
        """Crear servicio de productos que usa RDS"""
        
        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "ProductsServiceTaskDefinition",
            cpu=256,
            memory_limit_mib=512
        )
        
        # Log Group
        log_group = logs.LogGroup(
            self, "ProductsServiceLogGroupV5",
            log_group_name="/ecs/products-service-v5",
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Container
        container = task_definition.add_container(
            "ProductsServiceContainer",
            image=ecs.ContainerImage.from_registry("python:3.9-slim"),
            command=["python", "-c", """
import http.server
import socketserver
import json
import os

class ProductsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'service': 'products-service-v5',
                'status': 'healthy',
                'db_host': os.getenv('DB_HOST', 'localhost'),
                'db_port': os.getenv('DB_PORT', '5432'),
                'version': 'V5'
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/products':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'service': 'products-service-v5',
                'message': 'Products endpoint V5 - conectado a RDS PostgreSQL',
                'db_host': os.getenv('DB_HOST', 'localhost'),
                'data': ['PROD001: Paracetamol', 'PROD002: Ibuprofeno', 'PROD003: Termómetro']
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'service': 'products-service-v5', 'message': 'Products Service V5', 'path': self.path}
            self.wfile.write(json.dumps(response).encode())

with socketserver.TCPServer(('', 8080), ProductsHandler) as httpd:
    print('Products Service V5 running on port 8080')
    httpd.serve_forever()
            """],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="products-service",
                log_group=log_group
            ),
            environment={
                "SERVICE_NAME": "products-service-v5",
                "LOG_LEVEL": "INFO",
                "DB_HOST": self.database.instance_endpoint.hostname,
                "DB_PORT": str(self.database.instance_endpoint.port)
            },
            port_mappings=[
                ecs.PortMapping(
                    container_port=8080,
                    protocol=ecs.Protocol.TCP
                )
            ]
        )
        
        # Target Group
        target_group = elbv2.ApplicationTargetGroup(
            self, "ProductsServiceTargetGroup",
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            vpc=self.default_vpc,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                healthy_http_codes="200"
            )
        )
        
        # ECS Service
        service = ecs.FargateService(
            self, "ProductsService",
            cluster=self.ecs_cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[security_group],
            assign_public_ip=True
        )
        
        # Attach to ALB
        service.attach_to_application_target_group(target_group)
        
        # ALB Listener Rule
        self.alb_listener.add_target_groups(
            "ProductsServiceRule",
            target_groups=[target_group],
            conditions=[elbv2.ListenerCondition.path_patterns(["/products*"])],
            priority=100
        )

    def _create_auth_service(self, security_group):
        """Crear servicio de autenticación que usa RDS"""
        
        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "AuthServiceTaskDefinition",
            cpu=256,
            memory_limit_mib=512
        )
        
        # Log Group
        log_group = logs.LogGroup(
            self, "AuthServiceLogGroupV5",
            log_group_name="/ecs/auth-service-v5",
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Container
        container = task_definition.add_container(
            "AuthServiceContainer",
            image=ecs.ContainerImage.from_registry("python:3.9-slim"),
            command=["python", "-c", """
import http.server
import socketserver
import json
import os

class AuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'service': 'auth-service-v5',
                'status': 'healthy',
                'db_host': os.getenv('DB_HOST', 'localhost'),
                'db_port': os.getenv('DB_PORT', '5432'),
                'version': 'V5'
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/auth':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'service': 'auth-service-v5',
                'message': 'Auth endpoint V5 - conectado a RDS PostgreSQL',
                'db_host': os.getenv('DB_HOST', 'localhost'),
                'users': ['test_user', 'admin', 'remote_worker']
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'service': 'auth-service-v5', 'message': 'Auth Service V5', 'path': self.path}
            self.wfile.write(json.dumps(response).encode())

with socketserver.TCPServer(('', 8080), AuthHandler) as httpd:
    print('Auth Service V5 running on port 8080')
    httpd.serve_forever()
            """],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="auth-service",
                log_group=log_group
            ),
            environment={
                "SERVICE_NAME": "auth-service-v5",
                "LOG_LEVEL": "INFO",
                "DB_HOST": self.database.instance_endpoint.hostname,
                "DB_PORT": str(self.database.instance_endpoint.port)
            },
            port_mappings=[
                ecs.PortMapping(
                    container_port=8080,
                    protocol=ecs.Protocol.TCP
                )
            ]
        )
        
        # Target Group
        target_group = elbv2.ApplicationTargetGroup(
            self, "AuthServiceTargetGroup",
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            vpc=self.default_vpc,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                healthy_http_codes="200"
            )
        )
        
        # ECS Service
        service = ecs.FargateService(
            self, "AuthService",
            cluster=self.ecs_cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[security_group],
            assign_public_ip=True
        )
        
        # Attach to ALB
        service.attach_to_application_target_group(target_group)
        
        # ALB Listener Rule
        self.alb_listener.add_target_groups(
            "AuthServiceRule",
            target_groups=[target_group],
            conditions=[elbv2.ListenerCondition.path_patterns(["/auth*"])],
            priority=200
        )
