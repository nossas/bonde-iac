from typing import Dict, Optional, Any
from pydantic import BaseModel
import pulumi
import pulumi_kubernetes as k8s


class N8NConfig(BaseModel):
    name: str = "n8n"
    namespace: str
    image: str = "n8nio/n8n:latest"
    replicas: int = 1
    smtp_sender: Optional[str] = "N8N <tech@bonde.org>"
    # Webhook
    webhook_url: str
    # Service
    service_port: int = 80
    container_port: int = 5678
    service_type: str = "ClusterIP"
    # Recursos
    resources: Dict[str, Any] = {
        "requests": {"memory": "512Mi", "cpu": "250m"},
        "limits": {"memory": "1Gi", "cpu": "500m"},
    }


class N8NOrchestrator(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        config: N8NConfig,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:apps:N8NOrchestrator", name, {}, opts)

        self.config = config

        self.deployment = self._create_deployment()
        self.service = self._create_service()

        self.register_outputs(
            {
                "service_endpoint": f"{config.name}.{config.namespace}.svc.cluster.local",
                "webhook_url": config.webhook_url,
                "n8n_ui_url": f"http://{config.name}.{config.namespace}.svc.cluster.local:{config.service_port}",
            }
        )

    def _create_deployment(self) -> k8s.apps.v1.Deployment:
        """Deployment do N8N"""
        env_vars = []

        # Variáveis de ambiente fixas
        fixed_env_vars = {
            "DB_TYPE": "postgresdb",
            "DB_POSTGRESDB_SSL_ENABLED": "true",
            "DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED": "false",
            "WEBHOOK_URL": self.config.webhook_url,
            "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS": "true",
            "N8N_LOG_LEVEL": "debug",
            "N8N_PROTOCOL": "http",
            "N8N_PORT": str(self.config.container_port),
            "N8N_HOST": "0.0.0.0",
            "N8N_PROXY": "true",
            # SMTP
            "N8N_EMAIL_MODE": "smtp",
            "N8N_SMTP_SENDER": self.config.smtp_sender,
            "N8N_SMTP_SSL": "false",
            "N8N_SMTP_TLS": "true",
        }

        for key, value in fixed_env_vars.items():
            env_vars.append(k8s.core.v1.EnvVarArgs(name=key, value=value))

        # Database Secrets
        # Database
        database_secret: str = "n8n-database-secret"
        smtp_secret: str = "n8n-smtp-secret"
        webhook_secret: str = "n8n-webhook-secret"

        secret_vars = [
            ("DB_POSTGRESDB_DATABASE", database_secret),
            ("DB_POSTGRESDB_HOST", database_secret),
            ("DB_POSTGRESDB_PASSWORD", database_secret),
            ("DB_POSTGRESDB_PORT", database_secret),
            ("DB_POSTGRESDB_USER", database_secret),
            ("N8N_SMTP_HOST", smtp_secret),
            ("N8N_SMTP_PORT", smtp_secret),
            ("N8N_SMTP_USER", smtp_secret),
            ("N8N_SMTP_PASS", smtp_secret),
            ("N8N_WEBHOOK_SECRET", webhook_secret),
        ]

        for env_secret_name, env_secret_value in secret_vars:
            env_vars.append(
                k8s.core.v1.EnvVarArgs(
                    name=env_secret_name,
                    value_from=k8s.core.v1.EnvVarSourceArgs(
                        secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                            name=env_secret_value,
                            key=env_secret_name,
                        )
                    ),
                )
            )

        return k8s.apps.v1.Deployment(
            f"{self.config.name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.config.name,
                namespace=self.config.namespace,
                labels={"app": self.config.name},
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=self.config.replicas,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels={"app": self.config.name}
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        labels={"app": self.config.name}
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name="n8n",
                                image=self.config.image,
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=self.config.container_port
                                    )
                                ],
                                env=env_vars,
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    requests=self.config.resources.get("requests", {}),
                                    limits=self.config.resources.get("limits", {}),
                                ),
                                liveness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz",
                                        port=self.config.container_port,
                                    ),
                                    initial_delay_seconds=90,
                                    period_seconds=30,
                                ),
                                readiness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz",
                                        port=self.config.container_port,
                                    ),
                                    initial_delay_seconds=60,
                                    period_seconds=15,
                                ),
                            )
                        ]
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _create_service(self) -> k8s.core.v1.Service:
        """Service para o N8N"""
        return k8s.core.v1.Service(
            f"{self.config.name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.config.name,
                namespace=self.config.namespace,
                labels={"app": self.config.name},
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                selector={"app": self.config.name},
                ports=[
                    k8s.core.v1.ServicePortArgs(
                        port=self.config.service_port,
                        target_port=self.config.container_port,
                    )
                ],
                type=self.config.service_type,
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )
