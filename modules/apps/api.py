from typing import Dict, Optional, Any
import pulumi
import pulumi_kubernetes as k8s


class HasuraGateway(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        namespace: str,
        # Configurações específicas do Hasura
        image: str = "hasura/graphql-engine:latest",
        replicas: int = 2,
        enable_console: bool = True,
        # Dependências (micro-serviços) {"ENV_VAR_NAME": "SERVICE_URL"}
        env_vars: Optional[Dict[str, Any]] = None,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:apps:HasuraGateway", name, {}, opts)

        self.name = name
        self.namespace = namespace
        self.env_vars = env_vars
        self.enable_console = enable_console
        self.deployment = self._create_deployment(image, replicas)
        self.service = self._create_service()

        self.register_outputs(
            {
                "service_endpoint": f"{name}.{namespace}.svc.cluster.local",
                "graphql_url": f"http://{name}.{namespace}.svc.cluster.local:8080/v1/graphql",
                "console_url": (
                    f"http://{name}.{namespace}.svc.cluster.local:8080/console"
                    if enable_console
                    else None
                ),
            }
        )

    def _create_deployment(self, image: str, replicas: int) -> k8s.apps.v1.Deployment:
        """Deployment do Hasura"""
        env_vars = []

        # Add plan variables
        fixed_env_vars = {
            "HASURA_GRAPHQL_ENABLE_CONSOLE": str(self.enable_console).lower(),
            "HASURA_GRAPHQL_UNAUTHORIZED_ROLE": "anonymous",
            "HASURA_GRAPHQL_ENABLED_LOG_TYPES": "startup,query-log,http-log,webhook-log,websocket-log",
            "HASURA_GRAPHQL_LOG_LEVEL": "debug",
            "HASURA_GRAPHQL_CORS_DOMAIN": "*",
            "HASURA_GRAPHQL_INFER_FUNCTION_PERMISSIONS": "false",
            "PORT": "8080",
        }

        # Adicionar variáveis fixas
        for key, value in fixed_env_vars.items():
            env_vars.append(k8s.core.v1.EnvVarArgs(name=key, value=value))

        if self.env_vars:
            for env_var_name, env_var_value in self.env_vars.items():
                env_vars.append(
                    k8s.core.v1.EnvVarArgs(
                        name=env_var_name, value=env_var_value
                    )
                )

        # 2. Secrets essenciais do Hasura
        essential_secrets = [
            ("HASURA_GRAPHQL_ADMIN_SECRET", "hasura-admin-secret"),
            ("HASURA_GRAPHQL_DATABASE_URL", "bonde-database-url"),
            (
                "HASURA_GRAPHQL_VOTEPELOCLIMA_DATABASE_URL",
                "votepeloclima-database-url",
            ),
            ("HASURA_GRAPHQL_JWT_SECRET", "jwt-secret"),
            ("N8N_WEBHOOK_TRIGGER_POSTGRES_AUTH", "n8n-webhook-secret"),
        ]

        for env_name, secret_name in essential_secrets:
            env_vars.append(
                k8s.core.v1.EnvVarArgs(
                    name=env_name,
                    value_from=k8s.core.v1.EnvVarSourceArgs(
                        secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                            name=secret_name,
                            key=env_name,
                        )
                    ),
                )
            )

        return k8s.apps.v1.Deployment(
            f"{self.name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.name, namespace=self.namespace, labels={"app": self.name}
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=replicas,
                selector=k8s.meta.v1.LabelSelectorArgs(match_labels={"app": self.name}),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(labels={"app": self.name}),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name="hasura",
                                image=image,
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(container_port=8080)
                                ],
                                env=env_vars,
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    requests={"memory": "512Mi", "cpu": "250m"},
                                    limits={"memory": "1Gi", "cpu": "500m"},
                                ),
                                liveness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz", port=8080
                                    ),
                                    initial_delay_seconds=60,
                                    period_seconds=30,
                                ),
                                readiness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz", port=8080
                                    ),
                                    initial_delay_seconds=30,
                                    period_seconds=10,
                                ),
                            )
                        ]
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _create_service(self) -> k8s.core.v1.Service:
        """Service para o Hasura"""
        return k8s.core.v1.Service(
            f"{self.name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.name, namespace=self.namespace, labels={"app": self.name}
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                selector={"app": self.name},
                ports=[k8s.core.v1.ServicePortArgs(port=80, target_port=8080)],
                type="ClusterIP",
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )
